using bionicpro_auth.Components.Handlers;
using bionicpro_auth.Components.Handlers.Implementation;
using bionicpro_auth.Components.Middleware;


var builder = WebApplication.CreateBuilder(args);

builder.Services.AddLogging();
builder.Services.AddLogging(builder => builder.AddConsole());

// Add services to the container.

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

var app = builder.Build();

app.UseSwagger();
app.UseSwaggerUI();
app.UseCors("MyPolicy");

app.UseAuthentication();

app.MapControllers();

app.Run();