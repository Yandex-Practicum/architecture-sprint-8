using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.IdentityModel.Tokens;
using WebApplication1;
using WebApplication1.Authorize;

const string myAllowSpecificOrigins = "_myAllowSpecificOrigins";

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddTransient<IClaimsTransformation, RoleClaimsTransformation>();

builder.Services.AddCors(options =>
{
	options.AddPolicy(name: myAllowSpecificOrigins,
		policy =>
		{
			policy.AllowAnyMethod()
				.AllowAnyHeader()
				.AllowAnyOrigin()
				;
		});
});

// Add services to the container.
builder.Services.AddControllers();

// Learn more about configuring Swagger/OpenAPI at https://aka.ms/aspnetcore/swashbuckle
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var scheme = JwtBearerDefaults.AuthenticationScheme;

var keycloakSettings = builder.Configuration
	.GetSection(KeycloakSettings.Name)
	.Get<KeycloakSettings>()!;

builder.Services
	.AddAuthentication(scheme)
	.AddKeycloakJwtBearer(
		serviceName: keycloakSettings.ServiceName,
		realm: keycloakSettings.Realm,
		authenticationScheme: scheme,
		configureOptions: options =>
		{
			options.Authority = $"http://{keycloakSettings.ServiceName}/realms/{keycloakSettings.Realm}";

			options.RequireHttpsMetadata = false;
			options.TokenValidationParameters = new TokenValidationParameters
			{
				ValidateIssuer = false,
				ValidateAudience = false,
			};
		})
	;

var app = builder.Build();

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
	app.UseSwagger();
	app.UseSwaggerUI();
}

app.UseCors(myAllowSpecificOrigins);

app.UseAuthorization();

app.MapControllers();

app.Run();