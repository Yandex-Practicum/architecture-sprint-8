from fastapi import FastAPI, HTTPException, Query
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from clickhouse_driver import Client
import os

# FastAPI app
app = FastAPI(
    title="Prosthetics Reports API",
    description="API for accessing prosthetics reports from ClickHouse",
    version="1.2.0"
)

# ClickHouse connection settings
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "9000"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "admin")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "admin123")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "prosthetics_mart")

# Response models
class DailyReport(BaseModel):
    period_date: date
    device_id: str
    device_name: str
    device_type: str
    telemetry_count: int
    avg_battery_level: float
    min_battery_level: float
    max_battery_level: float
    avg_temperature: float
    max_temperature: float
    total_steps: int
    error_count: int
    active_hours: int
    device_health: Optional[float] = None

class ClientReport(BaseModel):
    client_external_id: str
    client_name: str
    email: str
    total_devices: int
    reports: List[DailyReport]
    period_start: date
    period_end: date
    generated_at: datetime

class ErrorResponse(BaseModel):
    detail: str
    error_code: str

# ClickHouse connection helper
def get_clickhouse_client():
    """Create and return ClickHouse client connection"""
    return Client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
        settings={'use_numpy': False}
    )

def calculate_device_health(report: dict) -> float:
    """Calculate device health score based on various metrics"""
    health_score = 100.0
    
    # Deduct points for errors
    health_score -= report.get('error_count', 0) * 5.0
    
    # Deduct points for low battery
    if report.get('min_battery_level', 100) < 20:
        health_score -= 10.0
    
    # Deduct points for high temperature
    if report.get('max_temperature', 0) > 40:
        health_score -= 15.0
    
    # Deduct points for high pressure
    if report.get('max_pressure', 0) > 50:
        health_score -= 10.0
    
    # Ensure score doesn't go below 0
    return max(health_score, 0.0)

def safe_query_execute(client: Client, query: str, params: dict = None):
    """Safely execute a ClickHouse query with parameters"""
    if params:
        # For ClickHouse, we need to format the query manually with safe escaping
        # ClickHouse driver doesn't support parameterized queries in the same way as PostgreSQL
        # We'll escape string parameters manually
        for key, value in params.items():
            if isinstance(value, str):
                # Escape single quotes in strings
                escaped_value = value.replace("'", "''")
                query = query.replace(f":{key}", f"'{escaped_value}'")
            elif isinstance(value, (date, datetime)):
                query = query.replace(f":{key}", f"'{value}'")
            elif value is None:
                query = query.replace(f":{key}", "NULL")
            else:
                query = query.replace(f":{key}", str(value))
    
    return client.execute(query)

@app.get("/reports", response_model=ClientReport, responses={
    404: {"model": ErrorResponse, "description": "Client not found or no data available"},
    400: {"model": ErrorResponse, "description": "Invalid parameters"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def get_reports(
    client_id: str = Query(..., description="External client ID (e.g., 'client_001')"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD). Defaults to 7 days ago"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD). Defaults to yesterday"),
    device_id: Optional[str] = Query(None, description="Filter by specific device ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return")
):
    """
    Get reports for a specific client from ClickHouse.
    
    Only returns data for periods that have been fully processed by ETL.
    By default, returns data from the last 7 days up to yesterday.
    """
    try:
        # Set default date range if not provided
        if end_date is None:
            end_date = date.today() - timedelta(days=1)  # Yesterday
        
        if start_date is None:
            start_date = end_date - timedelta(days=6)  # Last 7 days
        
        # Validate dates
        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date must be before or equal to end_date"
            )
        
        if end_date >= date.today():
            raise HTTPException(
                status_code=400,
                detail="end_date must be before today (data only available for fully processed days)"
            )
        
        # Connect to ClickHouse
        ch_client = get_clickhouse_client()
        
        # 1. First, check if client exists and get basic info
        # Using manual parameter replacement for ClickHouse
        client_query = """
        SELECT 
            external_client_id,
            concat(first_name, ' ', last_name) as client_name,
            email
        FROM clients_dimension 
        WHERE external_client_id = :client_id
        AND is_active = 1
        ORDER BY updated_at DESC
        LIMIT 1
        """
        
        client_result = safe_query_execute(ch_client, client_query, {'client_id': client_id})
        
        if not client_result:
            raise HTTPException(
                status_code=404,
                detail=f"Active client with ID '{client_id}' not found"
            )
        
        external_client_id, client_name, email = client_result[0]
        
        # 2. Count total active devices for this client
        # First get the client_id from clients_dimension
        get_client_id_query = """
        SELECT client_id 
        FROM clients_dimension 
        WHERE external_client_id = :client_id
        AND is_active = 1 
        LIMIT 1
        """
        
        client_id_result = safe_query_execute(ch_client, get_client_id_query, {'client_id': client_id})
        if not client_id_result:
            raise HTTPException(
                status_code=404,
                detail=f"Could not find internal client ID for external ID '{client_id}'"
            )
        
        internal_client_id = client_id_result[0][0]
        
        # Count devices for this client
        device_count_query = """
        SELECT count(distinct device_id) 
        FROM devices_dimension 
        WHERE client_id = :internal_client_id
        AND is_active = 1
        """
        
        device_count_result = safe_query_execute(ch_client, device_count_query, {'internal_client_id': internal_client_id})
        total_devices = device_count_result[0][0] if device_count_result else 0
        
        # 3. Get the report data from the daily mart table
        # Build the query with manual parameter replacement
        report_query = """
        SELECT 
            external_client_id,
            client_name,
            email,
            device_id,
            device_name,
            device_type,
            period_date,
            telemetry_count,
            avg_battery_level,
            min_battery_level,
            max_battery_level,
            avg_temperature,
            max_temperature,
            avg_pressure,
            max_pressure,
            avg_flexion_angle,
            max_flexion_angle,
            total_steps,
            error_count,
            active_hours,
            has_low_battery,
            has_high_temperature,
            has_pressure_alert,
            first_telemetry_time,
            last_telemetry_time
        FROM client_telemetry_daily_mart
        WHERE external_client_id = :client_id
            AND period_date BETWEEN :start_date AND :end_date
        """
        
        # Prepare parameters dictionary
        params = {
            'client_id': client_id,
            'start_date': start_date,
            'end_date': end_date
        }
        
        # Add device filter if provided
        if device_id:
            report_query += " AND device_id = :device_id"
            params['device_id'] = device_id
        
        report_query += " ORDER BY period_date DESC, device_id"
        report_query += " LIMIT :limit"
        params['limit'] = limit
        
        # Execute the query with manual parameter replacement
        report_data = safe_query_execute(ch_client, report_query, params)
        
        # 4. Format the response
        reports = []
        for row in report_data:
            report_dict = {
                'external_client_id': row[0],
                'client_name': row[1],
                'email': row[2],
                'device_id': row[3],
                'device_name': row[4],
                'device_type': row[5],
                'period_date': row[6],
                'telemetry_count': row[7],
                'avg_battery_level': float(row[8]) if row[8] is not None else 0.0,
                'min_battery_level': float(row[9]) if row[9] is not None else 0.0,
                'max_battery_level': float(row[10]) if row[10] is not None else 0.0,
                'avg_temperature': float(row[11]) if row[11] is not None else 0.0,
                'max_temperature': float(row[12]) if row[12] is not None else 0.0,
                'avg_pressure': float(row[13]) if row[13] is not None else 0.0,
                'max_pressure': float(row[14]) if row[14] is not None else 0.0,
                'avg_flexion_angle': float(row[15]) if row[15] is not None else 0.0,
                'max_flexion_angle': float(row[16]) if row[16] is not None else 0.0,
                'total_steps': row[17],
                'error_count': row[18],
                'active_hours': row[19],
                'has_low_battery': row[20],
                'has_high_temperature': row[21],
                'has_pressure_alert': row[22],
                'first_telemetry_time': row[23],
                'last_telemetry_time': row[24]
            }
            
            # Calculate device health
            device_health = calculate_device_health(report_dict)
            
            report = DailyReport(
                period_date=report_dict['period_date'],
                device_id=report_dict['device_id'],
                device_name=report_dict['device_name'],
                device_type=report_dict['device_type'],
                telemetry_count=report_dict['telemetry_count'],
                avg_battery_level=report_dict['avg_battery_level'],
                min_battery_level=report_dict['min_battery_level'],
                max_battery_level=report_dict['max_battery_level'],
                avg_temperature=report_dict['avg_temperature'],
                max_temperature=report_dict['max_temperature'],
                total_steps=report_dict['total_steps'],
                error_count=report_dict['error_count'],
                active_hours=report_dict['active_hours'],
                device_health=device_health
            )
            reports.append(report)
        
        # Close ClickHouse connection
        ch_client.disconnect()
        
        # 5. Return the response
        return ClientReport(
            client_external_id=external_client_id,
            client_name=client_name,
            email=email,
            total_devices=total_devices,
            reports=reports,
            period_start=start_date,
            period_end=end_date,
            generated_at=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving reports: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        ch_client = get_clickhouse_client()
        # Check if the mart table exists and has data
        result = ch_client.execute("""
            SELECT 
                (SELECT count() FROM clients_dimension) as client_count,
                (SELECT count() FROM devices_dimension) as device_count,
                (SELECT count() FROM client_telemetry_daily_mart) as report_count
        """)
        ch_client.disconnect()
        
        if result:
            client_count, device_count, report_count = result[0]
            return {
                "status": "healthy",
                "database": "connected",
                "data_summary": {
                    "clients": client_count,
                    "devices": device_count,
                    "reports": report_count
                },
                "timestamp": datetime.now().isoformat()
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service unhealthy: {str(e)}"
        )

@app.get("/test-query")
async def test_query():
    """Test ClickHouse query execution"""
    try:
        ch_client = get_clickhouse_client()
        
        # Test 1: Simple query
        simple_result = ch_client.execute("SELECT 1 as test_value")
        
        # Test 2: Check if tables exist
        tables_result = ch_client.execute("SHOW TABLES")
        
        # Test 3: Try to query the mart table
        mart_query = "SELECT count() as count FROM client_telemetry_daily_mart"
        mart_result = ch_client.execute(mart_query)
        
        # Test 4: Try with a parameter (manually formatted)
        test_client_id = "client_001"
        test_query = f"""
        SELECT external_client_id, client_name, email
        FROM clients_dimension 
        WHERE external_client_id = '{test_client_id}'
        LIMIT 1
        """
        param_result = ch_client.execute(test_query)
        
        ch_client.disconnect()
        
        return {
            "status": "success",
            "simple_query": simple_result,
            "tables": tables_result,
            "mart_table_count": mart_result,
            "parameter_query_result": param_result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Test query failed: {str(e)}"
        )

@app.get("/check-mart-data")
async def check_mart_data():
    """Check what data is available in the mart table"""
    try:
        ch_client = get_clickhouse_client()
        
        # Get sample data from mart table
        sample_query = """
        SELECT 
            external_client_id,
            client_name,
            count() as report_count,
            min(period_date) as earliest_date,
            max(period_date) as latest_date
        FROM client_telemetry_daily_mart
        GROUP BY external_client_id, client_name
        ORDER BY report_count DESC
        LIMIT 10
        """
        
        sample_data = ch_client.execute(sample_query)
        
        # Check if we have any data
        count_query = "SELECT count() FROM client_telemetry_daily_mart"
        total_count = ch_client.execute(count_query)[0][0]
        
        ch_client.disconnect()
        
        return {
            "status": "success",
            "total_records": total_count,
            "sample_data": [
                {
                    "client_id": row[0],
                    "client_name": row[1],
                    "report_count": row[2],
                    "date_range": f"{row[3]} to {row[4]}"
                }
                for row in sample_data
            ],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check mart data: {str(e)}"
        )

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Prosthetics Reports API",
        "version": "1.2.0",
        "endpoints": {
            "GET /reports": "Get reports for a client",
            "GET /health": "Health check",
            "GET /test-query": "Test ClickHouse queries",
            "GET /check-mart-data": "Check available data in mart table",
            "GET /": "This information"
        },
        "documentation": "/docs"
    }