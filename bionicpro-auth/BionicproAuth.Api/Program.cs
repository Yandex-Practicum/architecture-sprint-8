using BionicproAuth.Api.Midlewares;
using BionicproAuth.Api.Services;
using BionicproAuth.Api.Session;

var  MyAllowSpecificOrigins = "FrontendPolicy";
var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
// Learn more about configuring OpenAPI at https://aka.ms/aspnet/openapi
builder.Services.AddOpenApi();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddControllers();
builder.Services.AddScoped<ISessionManager, InMemorySessionManager >();
builder.Services.AddScoped<ITokenService, TokenService >();
builder.Services.AddHttpClient<ITokenExchangeService, TokenExchangeService>();
builder.Services.AddScoped<ITokenExchangeService, TokenExchangeService>();
builder.Services.AddMemoryCache();
builder.Services.AddHttpClient();
builder.Services.AddDataProtection();
builder.Services.AddCors(options =>
{
    options.AddPolicy(name: MyAllowSpecificOrigins,
        policy  =>
        {
            policy.WithOrigins("http://localhost:3000")
                .AllowCredentials()           
                .AllowAnyHeader()
                .AllowAnyMethod();
        });
});


var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

app.UseHttpsRedirection();
app.UseCors(MyAllowSpecificOrigins);
app.UseMiddleware<SessionMiddleware>();

app.MapControllers();


app.MapGet("/auth", () =>
    {
       
        return ;
    })
    .WithName("Auth");

app.Run();

