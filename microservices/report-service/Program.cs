using report_service.Services;
using Serilog;
using Microsoft.AspNetCore.Authentication.JwtBearer;

var builder = WebApplication.CreateBuilder(args);

builder.Host.UseSerilog((ctx, cfg) =>
    cfg.ReadFrom.Configuration(ctx.Configuration));

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.Authority = "http://keycloak:8089/realms/reports-realm";
        options.RequireHttpsMetadata = false;
        options.Audience = "reports-api";
    });

builder.Services.AddAuthorization();

builder.Services.AddControllers();
builder.Services.AddScoped<IClickHouseRepository, ClickHouseRepository>();
builder.Services.AddScoped<IReportService, ReportService>();
builder.Services.AddScoped<IS3Service, S3Service>();

var app = builder.Build();

app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();

app.Run("http://0.0.0.0:8086");