using bionicpro_auth.Components.Handlers;
using bionicpro_auth.Components.Handlers.Implementation;
using bionicpro_auth.Components.Middleware;
using Microsoft.AspNetCore.OpenApi;
using NETCore.Keycloak.Client.Authentication;
using NETCore.Keycloak.Client.HttpClients.Abstraction;
using NETCore.Keycloak.Client.HttpClients.Implementation;
using NETCore.Keycloak.Client.Models.KcEnum;


var builder = WebApplication.CreateBuilder(args);

// Add services to the container.

builder.Services.AddKeycloakAuthentication(
    authenticationScheme: "Bearer", // Optional, defaults to "Bearer"
    keycloakConfig: options =>
    {
        options.Url = builder.Configuration["Keycloak:auth-server-url"];          // Keycloak base URL
        options.Issuer = builder.Configuration["Keycloak:auth-server-url"];       // Keycloak issuer URL (usually same as base URL)
        options.Realm = builder.Configuration["Keycloak:realm"];                    // Your Keycloak realm
        options.RolesSource = KcRolesClaimSource.Realm;  // Where to source role claims from
        options.RoleClaimType = "roles";                 // Claim type for roles
    });

builder.Services.AddScoped<IKeycloakClient, KeycloakClient>(sp => new KeycloakClient(sp.GetService<IConfiguration>()!["Keycloak:auth-server-url"]));

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

var app = builder.Build();

app.UseSwagger();
app.UseSwaggerUI();


app.UseAuthentication();

app.MapControllers();

app.Run();