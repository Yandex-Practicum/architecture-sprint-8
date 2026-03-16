using System.Security.Claims;
using BionicproReport;
using BionicproReport.Services;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using QuestPDF.Infrastructure;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
// Learn more about configuring OpenAPI at https://aka.ms/aspnet/openapi
builder.Services.AddOpenApi();

// Add services to the container.
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddScoped<IReportStorage, S3ReportStorage>();
builder.Services.AddScoped<IClickHouseReportService, ClickHouseReportService>();

// JWT Authentication
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.Authority = builder.Configuration["Keycloak:Authority"];
        options.Audience = builder.Configuration["Keycloak:ReportsApi:ClientId"]; // аудитория должна совпадать с client_id
        options.RequireHttpsMetadata = false; // для разработки
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuer = builder.Configuration["Keycloak:Authority"],
            ValidateAudience = true,
            ValidAudience = builder.Configuration["Keycloak:ReportsApi:ClientId"],
            ValidateLifetime = true,
            NameClaimType = "sub" // чтобы User.Identity.Name заполнялся sub
        };
        options.Events = new JwtBearerEvents()
        {
            OnTokenValidated = (context) =>
            {
                if (context.Principal?.Identity is ClaimsIdentity identity)
                {
                    identity.AddClaim(new Claim("sub", "19"));
                }


                return Task.CompletedTask;
            }
        };
    });

// Database connection (Dapper)
builder.Services.AddSingleton<DapperContext>(); // предполагается наличие класса DapperContext

builder.Services.AddAuthorization();

QuestPDF.Settings.License = LicenseType.Community;
var app = builder.Build();





app.UseHttpsRedirection();
app.UseAuthentication();
app.UseAuthorization();
app.MapControllers();

app.Run();

