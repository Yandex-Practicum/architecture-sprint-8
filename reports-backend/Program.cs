
using ClickHouse.Client.ADO;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using reports_backend.Services;
using System.Reflection;
using System.Security.Claims;
using System.Text;

namespace reports_backend
{
    public class Program
    {
        public static void Main(string[] args)
        {
            using var loggerFactory = LoggerFactory.Create(builder =>
            {
                builder.AddConsole();
                builder.SetMinimumLevel(LogLevel.Debug);
            });
            ILogger logger = loggerFactory.CreateLogger("Startup");
            logger.LogInformation("Performing pre-build initialization...");

            var builder = WebApplication.CreateBuilder(args);

            // Add services to the container.

            builder.Services.AddControllers();
            // Learn more about configuring Swagger/OpenAPI at https://aka.ms/aspnetcore/swashbuckle
            builder.Services.AddEndpointsApiExplorer();
            builder.Services.AddSwaggerGen(options =>
                {
                    options.AddSecurityDefinition("Bearer", new Microsoft.OpenApi.Models.OpenApiSecurityScheme
                    {
                        Name = "Authorization",
                        Type = Microsoft.OpenApi.Models.SecuritySchemeType.Http,
                        Scheme = "Bearer",
                        BearerFormat = "JWT",
                        In = Microsoft.OpenApi.Models.ParameterLocation.Header,
                        Description = "Введите только JWT токен. Пример: 12345abcdef"
                    });

                    // Делаем авторизацию глобальной для всех эндпоинтов с атрибутом [Authorize]
                    options.AddSecurityRequirement(new Microsoft.OpenApi.Models.OpenApiSecurityRequirement
                    {
                        {
                            new Microsoft.OpenApi.Models.OpenApiSecurityScheme
                            {
                                Reference = new Microsoft.OpenApi.Models.OpenApiReference
                                {
                                    Type = Microsoft.OpenApi.Models.ReferenceType.SecurityScheme,
                                    Id = "Bearer"
                                }
                            },
                        Array.Empty<string>()
                        }
                    });
                });
            Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);


            // см. ClickHouseConnectionStringBuilder()
            var host = builder.Configuration["CLICKHOUSE_HOST"];
            var port = builder.Configuration["CLICKHOUSE_PORT"];
            var db = builder.Configuration["CLICKHOUSE_DB"];
            var user = builder.Configuration["CLICKHOUSE_USER"];
            var pass = builder.Configuration["CLICKHOUSE_PASSWORD"];

            var connectionString = $"Protocol=http;Host={host};Port={port};Username={user};Password={pass};Database={db};";

            builder.Services.AddSingleton(new ClickHouseDataSource(connectionString));
            builder.Services.AddScoped<IClickhouseCLientService, ClickHouseService>();


            var authority_url = builder.Configuration["Keycloak:AuthorityURL"]; // realm url
            var audience_info_url = builder.Configuration["Keycloak:MetadataURL"]; //metadata: auth points, public keys
            // целевой издатель сертификата. Используем ссылку на realm
            var valid_issuer = builder.Configuration["Keycloak:ValidIssuer"];
            var valid_audinece = builder.Configuration["Keycloak:ValidAudience"];
            builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
            .AddJwtBearer(jwtOptions =>
            {
                jwtOptions.RequireHttpsMetadata = false;//true;
                jwtOptions.UseSecurityTokenValidators = true;
                jwtOptions.Authority = authority_url;
                jwtOptions.Audience = audience_info_url;
                jwtOptions.TokenValidationParameters = new TokenValidationParameters
                {
                    ValidIssuers = [valid_issuer],
                    ValidateIssuerSigningKey = true,

                    NameClaimType = ClaimTypes.Name,
                    RoleClaimType = ClaimTypes.Role,
                    ValidateIssuer = true,
                    ValidateAudience = true,
                    ValidateLifetime = true,
                    ValidAudience = valid_audinece
                };


                jwtOptions.Events = new JwtBearerEvents
                    {
                        OnTokenValidated = context => {
                            logger.LogInformation("Token validated");
                            // Breakpoint here to inspect successful user claims
                            return Task.CompletedTask;
                        },
                        OnAuthenticationFailed = context => {
                            var exception = context.Exception;
                            logger.LogInformation($"Token check failed with exception: {exception.Message}");

                            return Task.CompletedTask;
                        },
                        OnMessageReceived = context => {
                            logger.LogInformation($"Auth query received for requset: {context.Request.Path}");
                            // Check if the token is even being extracted
                            return Task.CompletedTask;
                        },
                        OnChallenge = context => {
                            logger.LogInformation("Challenge detected");

                            return Task.CompletedTask;
                        },
                        OnForbidden = context => {
                            logger.LogInformation("Auth failed");

                            return Task.CompletedTask;
                        },
                };
            });
            var frontendURL = builder.Configuration["FrontendURL"];
            builder.Services.AddCors(options =>
            {
                options.AddPolicy("AllowFrontend", policy =>
                {
                    policy.WithOrigins(frontendURL) // Адрес вашего фронтенда
                          .AllowAnyHeader()
                          .AllowAnyMethod();
                });
            });

            var app = builder.Build();
            app.UseCors("AllowFrontend");

            // Configure the HTTP request pipeline.
            if (app.Environment.IsDevelopment())
            {
                app.UseSwagger();
                app.UseSwaggerUI();
            }
            app.UseAuthentication();
            app.UseAuthorization();

            //app.UseHttpsRedirection();
            app.MapControllers();

            app.Run();
        }
    }
}
