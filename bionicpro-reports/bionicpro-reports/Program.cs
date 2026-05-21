using Amazon.S3;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.DataProtection;

namespace bionicpro_reports
{
    public class Program
    {
        public static void Main(string[] args)
        {
            var builder = WebApplication.CreateBuilder(args);

            // ============================================================
            // НАСТРОЙКА И РЕГИСТРАЦИЯ КЛИЕНТА S3 (MinIO)
            // ============================================================
            var s3Config = new AmazonS3Config
            {
                // Используем имя контейнера "minio" как хост внутри сети Docker
                ServiceURL = "http://minio:9000",
                ForcePathStyle = true // Критично для корректной работы с MinIO/Ceph вместо AWS
            };

            // Регистрируем Singleton-сервис в контейнере зависимостей
            builder.Services.AddSingleton<IAmazonS3>(new AmazonS3Client("minio_admin", "minio_password", s3Config));
            // ============================================================



            // 1. НАСТРОЙКА DATA PROTECTION (Критически важно для общего чтения Кук!)
            // Оба сервиса (auth и reports) должны смотреть в одну папку с ключами
            builder.Services.AddDataProtection()
                .PersistKeysToFileSystem(new DirectoryInfo(@"/app/shared-auth-keys/"))
                .SetApplicationName("bionicpro_shared_auth");

            // 2. НАСТРОЙКА АУТЕНТИФИКАЦИИ (Дублируем настройки куки из сервиса auth)
            builder.Services.AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
                .AddCookie(CookieAuthenticationDefaults.AuthenticationScheme, options =>
                {
                    options.Cookie.Name = "reports_session"; // Имя должно совпадать!
                    options.Cookie.HttpOnly = true;
                    // Если сервисы на разных портах/доменах, настройте SameSite и Domain:
                    options.Cookie.SameSite = SameSiteMode.Lax;

                    // Включите менеджер разбиения кук на чанки!
                    options.CookieManager = new Microsoft.AspNetCore.Authentication.Cookies.ChunkingCookieManager();

                });

            builder.Services.AddAuthorization();
            builder.Services.AddControllers();
            builder.Services.AddOpenApi();

            // Настройка CORS (синхронно с вашим фронтендом)
            builder.Services.AddCors(options =>
            {
                options.AddPolicy("AllowFrontendWithCookies", policy =>
                {
                    policy.SetIsOriginAllowed(origin => true)
                          .AllowAnyMethod()
                          .AllowAnyHeader()
                          .AllowCredentials();
                });
            });

            var app = builder.Build();

            app.UseCors("AllowFrontendWithCookies");

            if (app.Environment.IsDevelopment())
            {
                app.MapOpenApi();
                app.UseSwaggerUI(options =>
                {
                    options.SwaggerEndpoint("/openapi/v1.json", "BionicPro Reports API v1");
                });
            }

            // Конвейер авторизации
            app.UseAuthentication();
            app.UseAuthorization();

            app.MapControllers();
            app.Run();
        }
    }
}
