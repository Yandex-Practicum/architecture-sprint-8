using Npgsql;

namespace BionicproReport;

public class DapperContext
{
    private readonly IConfiguration _configuration;
    private readonly string _connectionString;

    public DapperContext(IConfiguration configuration)
    {
        _configuration = configuration;
        _connectionString = _configuration.GetConnectionString("ReportingDb");
    }

    public NpgsqlConnection CreateConnection() => new NpgsqlConnection(_connectionString);
}