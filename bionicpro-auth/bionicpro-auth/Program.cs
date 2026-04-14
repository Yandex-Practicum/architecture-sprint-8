using bionicpro_auth.Components.Handlers;
using bionicpro_auth.Components.Handlers.Implementation;
using bionicpro_auth.Components.Middleware;
using bionicpro_auth.Models.Settings;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authentication.JwtBearer;


var builder = WebApplication.CreateBuilder(args);

builder.Services.AddLogging();
builder.Services.AddLogging(builder => builder.AddConsole());

// Add services to the container.

builder.Services.Configure<AppSettings>(builder.Configuration.GetSection("App"));
builder.Services.Configure<KeycloakSettings>(builder.Configuration.GetSection("Keycloak"));
builder.Services.Configure<SessionSettings>(builder.Configuration.GetSection("Session"));

builder.Services.AddHttpClient<IKeyCloakService, KeycloakService>();

builder.Services.AddSingleton<IEncryptor>((_) => AesEncryptor.Init());
builder.Services.AddScoped<ICacheWrapper, CacheWrapper>();
builder.Services.AddScoped<ISessionService, SessionService>();
builder.Services.AddScoped<IKeyCloakService, KeycloakService>();
builder.Services.AddScoped<IAuthService, AuthService>();
builder.Services.AddScoped<IContextWrapper, ContextWrapper>();

builder.Services.AddScoped<SessionRotateAttribute>();

builder.Services.AddMemoryCache();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddControllers();

builder.Services.AddCors(options =>
    {
        options.AddPolicy("MyPolicy", builder =>
        {
            builder
                .WithOrigins("https://front.bio-pro.local:444")
                .AllowCredentials()
                .AllowAnyHeader()
                .AllowAnyMethod();
        });
    });


// Настройка аутентификации через cookies (для сессий)
builder.Services.AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
    .AddCookie(options =>
    {
        options.Cookie.Name = builder.Configuration["Authentication:Cookie:Name"];
        options.Cookie.HttpOnly = true;
        options.Cookie.SameSite = SameSiteMode.Strict;
        options.Cookie.SecurePolicy = CookieSecurePolicy.Always;
        options.ExpireTimeSpan = TimeSpan.FromMinutes(
            double.Parse(builder.Configuration["Authentication:Cookie:ExpireTimeMinutes"] ?? "15"));
        options.SlidingExpiration = true;
        options.Events = new CookieAuthenticationEvents
        {
            OnRedirectToLogin = context =>
            {
                context.Response.StatusCode = 401;
                return Task.CompletedTask;
            }
        };
    });

// Настройка JWT Bearer для API
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.Authority = $"{builder.Configuration["Keycloak:BaseUrl"]}/realms/{builder.Configuration["Keycloak:Realm"]}";
        options.Audience = builder.Configuration["Keycloak:BackendClientId"];
        options.RequireHttpsMetadata = false; // Только для разработки
        options.TokenValidationParameters = new Microsoft.IdentityModel.Tokens.TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuer = $"{builder.Configuration["Keycloak:BaseUrl"]}/realms/{builder.Configuration["Keycloak:Realm"]}",
            ValidateAudience = true,
            ValidAudience = builder.Configuration["Keycloak:BackendClientId"],
            ValidateLifetime = true
        };
    });


var app = builder.Build();
app.UseSwagger();
app.UseSwaggerUI();
app.UseCors("MyPolicy");

app.UseAuthentication();

app.MapControllers();

app.Run();