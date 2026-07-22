using bionicpro_auth_api.Middleware;
using bionicpro_auth_api.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();

builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = builder.Configuration["Redis:ConnectionString"] ?? "redis:6379";
    options.InstanceName = "bionicpro:";
});

builder.Services.AddScoped<ITokenStorage, RedisTokenStorage>();
builder.Services.AddScoped<IKeycloakService, KeycloakService>();
builder.Services.AddHttpClient<IKeycloakService, KeycloakService>();

builder.Services.AddSession(options =>
{
    options.IdleTimeout = TimeSpan.FromMinutes(60);
    options.Cookie.HttpOnly = true;
    options.Cookie.SecurePolicy = CookieSecurePolicy.None;
    options.Cookie.SameSite = SameSiteMode.Lax;
    options.Cookie.Name = ".BionicPro.Session";
});

builder.Services.AddReverseProxy()
    .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"));

builder.Services.AddCors(options =>
{
    options.AddPolicy("Frontend", policy =>
    {
        policy.WithOrigins("http://localhost:3000", "http://localhost:8000")
              .AllowCredentials()
              .AllowAnyHeader()
              .AllowAnyMethod();
    });
});

var app = builder.Build();

app.UseCors("Frontend");

app.UseSession();

app.UseMiddleware<TokenManagementMiddleware>();
app.UseMiddleware<SessionRotationMiddleware>();

app.MapControllers();
app.MapReverseProxy();

app.Run();