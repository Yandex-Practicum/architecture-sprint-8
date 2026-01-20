using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using System.IdentityModel.Tokens.Jwt;
using Microsoft.IdentityModel.Tokens;

var builder = WebApplication.CreateBuilder(args);

// Конфигурация
builder.Configuration
    .AddJsonFile("appsettings.json", optional: false, reloadOnChange: true);

// Добавляем CORS
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowFrontend", builder =>
    {
        builder
            .WithOrigins("http://localhost:3000")
            .AllowAnyHeader()
            .AllowAnyMethod()
            .AllowCredentials();
    });
});

// Добавляем аутентификацию JWT
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.Authority = builder.Configuration["Keycloak:Authority"];
        options.RequireHttpsMetadata = false;
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateAudience = true,
            ValidateIssuer = true,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer = builder.Configuration["Keycloak:Issuer"],
            ValidAudience = builder.Configuration["Keycloak:Audience"],
            NameClaimType = "preferred_username"
        };
        options.Events = new JwtBearerEvents
        {
            OnMessageReceived = context =>
            {
                var authHeader = context.Request.Headers["Authorization"];
                var authHeaderValue = authHeader.ToString();
                if (!string.IsNullOrEmpty(authHeaderValue) && authHeaderValue.StartsWith("Bearer "))
                {
                    context.Token = authHeaderValue.Substring("Bearer ".Length).Trim();
                }
                return Task.CompletedTask;
            }
        };
    });

// Добавляем авторизацию
builder.Services.AddAuthorization();

// Добавляем маршрутизацию
builder.Services.AddControllers();

var app = builder.Build();

// Конфигурируем middleware
app.UseRouting();
app.UseCors("AllowFrontend");
app.UseAuthentication();
app.UseAuthorization();

// Конфигурируем конечные точки
app.MapControllers();

// Запуск приложения
app.Run();
