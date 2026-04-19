using bionicpro_report.Components;
using bionicpro_report.Components.Implementation;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using Minio;
using System.Net;

var builder = WebApplication.CreateBuilder(args);


builder.Services.AddSingleton<IReportService, ReportService>();
builder.Services.AddSingleton<IClickHouseService, ClickHouseService>();
builder.Services.AddSingleton<IS3Storage, S3Storage>();

builder.Services.AddMinio(client =>
{
    client.WithEndpoint(builder.Configuration["Minio:Endpoint"])
        .WithCredentials(builder.Configuration["Minio:AccessKey"], builder.Configuration["Minio:SecretKey"])
        .WithSSL(false);
});

builder.Services.AddAuthorization();
builder.Services.AddControllers();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new() { Title = "BionicPro Report API", Version = "v1" });
});


var app = builder.Build();



app.UseSwagger();
app.UseSwaggerUI();

app.MapControllers();


app.MapControllers();

app.Run();