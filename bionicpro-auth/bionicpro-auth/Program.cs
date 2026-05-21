using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authentication.OpenIdConnect;
using Microsoft.AspNetCore.DataProtection; 
using Microsoft.IdentityModel.Protocols.OpenIdConnect;

namespace bionicpro_auth
{
    public class Program
    {
        public static void Main(string[] args)
        {
            var builder = WebApplication.CreateBuilder(args);

            builder.Services.AddHttpClient();
            builder.Services.AddScoped<CookieOidcRefresher>();

            // ============================================================
            // НАСТРОЙКА DATA PROTECTION ДЛЯ ОБЩИХ КУК
            // ============================================================
            // Путь к папке должен быть одинаковым во всех микросервисах
            builder.Services.AddDataProtection()
                .PersistKeysToFileSystem(new DirectoryInfo(@"/app/shared-auth-keys/"))
                .SetApplicationName("bionicpro_shared_auth");
            // ============================================================

            // Настраиваем Cors (Используется только для учебных целей!)
            builder.Services.AddCors(options =>
            {
                options.AddPolicy("AllowAllWithCookiesPolicy", policy =>
                {
                    policy.SetIsOriginAllowed(origin => true) // Разрешает абсолютно любой Origin динамически
                          .AllowAnyMethod()
                          .AllowAnyHeader()
                          .AllowCredentials(); // Позволяет передавать куки сессии
                });
            });

            // 1. Добавляем сервисы для работы контроллеров и сессий страниц
            builder.Services.AddControllersWithViews();

            // 2. Настраиваем комбинированную схему аутентификации (Сессия Cookie + Проверка Keycloak)
            builder.Services.AddAuthentication(options =>
            {
                options.DefaultScheme = CookieAuthenticationDefaults.AuthenticationScheme;
                options.DefaultChallengeScheme = OpenIdConnectDefaults.AuthenticationScheme;
            })
            .AddCookie(CookieAuthenticationDefaults.AuthenticationScheme, options =>
            {
                options.Cookie.Name = "reports_session";            // Имя куки сессии
                options.Cookie.HttpOnly = true;                     // Защита от XSS атак
                options.ExpireTimeSpan = TimeSpan.FromMinutes(30);  // Время жизни сессии на бэкенде
                options.SlidingExpiration = true;                   // Продлевать сессию при активности

                // Настройка домена куки для возможности чтения другим микросервисом
                options.Cookie.SameSite = SameSiteMode.Lax;

                // Включите менеджер разбиения кук на чанки!
                options.CookieManager = new Microsoft.AspNetCore.Authentication.Cookies.ChunkingCookieManager();

                options.EventsType = typeof(CookieOidcRefresher);   //Связываем куку с нашей логикой автопродления токенов
            })
            .AddOpenIdConnect(OpenIdConnectDefaults.AuthenticationScheme, options =>
            {
                options.MetadataAddress = builder.Configuration["Keycloak:MetadataAddress"];
                options.Authority = builder.Configuration["Keycloak:Authority"];

                // Данные клиента-фронтенда
                options.ClientId = "reports-frontend";
                options.ClientSecret = "";                                  // Публичный клиент, секрет не нужен
                options.ResponseType = OpenIdConnectResponseType.Code;      // Поток Authorization Code

                // ============================================================
                // КРИТИЧЕСКИ ВАЖНО ДЛЯ .NET 9: Отключаем принудительный PAR
                // ============================================================
                options.PushedAuthorizationBehavior = PushedAuthorizationBehavior.Disable;
                options.UsePkce = true;                                     // Включаем поддержку PKCE
                options.RefreshOnIssuerKeyNotFound = true;                  // Ожидание keycloack
                options.RequireHttpsMetadata = false;                       // Отключено только для локального localhost
                options.SaveTokens = false;                                  // Важно! Сохраняет JWT (access, refresh tokens) внутри сессии cookie

                // Настройка Scopes (запрашиваемые данные)
                options.Scope.Clear();
                options.Scope.Add("openid");
                options.Scope.Add("profile");
                options.Scope.Add("email");

                // Событие: Что делать при выходе из системы (Logout)
                options.Events = new OpenIdConnectEvents
                {
                    OnRedirectToIdentityProviderForSignOut = context =>
                    {
                        // Корректный эндпоинт завершения сессии в самом Keycloak
                        var logoutUri = $"{context.Options.Authority}/protocol/openid-connect/logout";
                        context.ProtocolMessage.IssuerAddress = logoutUri;
                        return Task.CompletedTask;
                    }
                };
            });

            // Learn more about configuring OpenAPI at https://aka.ms/aspnet/openapi
            builder.Services.AddOpenApi();

            var app = builder.Build();

            app.UseCors("AllowAllWithCookiesPolicy");
            app.UseRouting();

            // Configure the HTTP request pipeline.
            if (app.Environment.IsDevelopment())
            {
                app.MapOpenApi();

                app.UseSwaggerUI(options =>
                {
                    options.SwaggerEndpoint("/openapi/v1.json", "BionicPro Auth API v1");
                });
            }

            // 3. Подключаем конвейер безопасности (Middlewares)
            app.UseAuthentication(); // Восстанавливает сессию из Cookie или идет в Keycloak
            app.UseAuthorization();  // Проверяет права

            app.MapControllers();

            app.MapControllerRoute(
                name: "default",
                pattern: "{controller=Home}/{action=Index}/{id?}");

            app.Run();
        }
    }
}
