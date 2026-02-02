from fastapi import FastAPI, HTTPException, Query, Request
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from clickhouse_driver import Client
import os
import jwt
from fastapi.middleware.cors import CORSMiddleware

# FastAPI app
app = FastAPI(
    title="Prosthetics Reports API",
    description="API for accessing prosthetics reports from ClickHouse",
    version="1.2.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins – change in production!
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allows all headers (Authorization, Content-Type, etc.)
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

# --- Security: Verify that username in token matches client_id ---
def verify_access_token(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]
    try:
        # Decode without verification (we trust Keycloak issued it)
        # In production, use public key to verify signature
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def verify_client_access(request: Request, client_id: str):
    payload = verify_access_token(request)
    username = payload.get("preferred_username")  # or "sub" if you prefer
    if not username:
        raise HTTPException(status_code=401, detail="Token does not contain username")

    if username != client_id:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: you can only access your own data (expected client_id={username})"
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

@app.get("/report", response_model=ClientReport, responses={
    404: {"model": ErrorResponse, "description": "Client not found or no data available"},
    400: {"model": ErrorResponse, "description": "Invalid parameters"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
async def get_report(
    request: Request,
    client_id: str = Query(..., description="External client ID (e.g., 'client_001')"),
    report_date: date = Query(..., description="Report date (YYYY-MM-DD)"),
    device_id: Optional[str] = Query(None, description="Filter by specific device ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return")
):
    """
    Get report for a specific client and date from ClickHouse.
    
    Returns data only for the specified date if available.
    """
    verify_client_access(request, client_id) 
    try:
        # Validate date - allow today, but block future dates
        if report_date > date.today():
            raise HTTPException(
                status_code=400,
                detail="report_date cannot be in the future"
            )
        
        # Connect to ClickHouse
        ch_client = get_clickhouse_client()
        
        # 1. First, check if client exists and get basic info
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
        
        # 3. Get the report data from the daily mart table for the specific date
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
            AND period_date = :report_date
        """
        
        # Add device filter if provided
        params = {
            'client_id': client_id,
            'report_date': report_date
        }
        
        if device_id:
            report_query += " AND device_id = :device_id"
            params['device_id'] = device_id
        
        report_query += " ORDER BY device_id"
        report_query += " LIMIT :limit"
        params['limit'] = limit
        
        # Execute the query
        report_data = safe_query_execute(ch_client, report_query, params)
        
        # Check if we have data for this date
        if not report_data:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for client '{client_id}' on date {report_date}"
            )
        
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
            period_start=report_date,
            period_end=report_date,
            generated_at=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving report: {str(e)}"
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