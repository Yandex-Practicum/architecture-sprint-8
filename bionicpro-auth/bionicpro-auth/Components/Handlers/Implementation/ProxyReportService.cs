using System.Text;
using System.Text.Json;

namespace bionicpro_auth.Components.Handlers.Implementation
{

    public class ReportsProxyService : IReportsProxyService
    {
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly IConfiguration _config;
        private readonly ILogger<ReportsProxyService> _logger;

        public ReportsProxyService(
            IHttpClientFactory httpClientFactory,
            IConfiguration config,
            ILogger<ReportsProxyService> logger)
        {
            _httpClientFactory = httpClientFactory;
            _config = config;
            _logger = logger;
        }

        private HttpClient CreateClient()
        {
            var client = _httpClientFactory.CreateClient("ReportsApi");
            client.Timeout = TimeSpan.FromSeconds(_config.GetValue<int>("ReportsApi:TimeoutSeconds", 300));
            return client;
        }

        private void AddAuthorizationHeader(HttpClient client, string accessToken)
        {
            client.DefaultRequestHeaders.Clear();
            client.DefaultRequestHeaders.Add("Authorization", $"Bearer {accessToken}");
            client.DefaultRequestHeaders.Add("X-Forwarded-For", "auth-api");
        }

        public async Task<HttpResponseMessage> ProxyGetAsync(string path, string accessToken)
        {
            using var client = CreateClient();
            AddAuthorizationHeader(client, accessToken);

            _logger.LogInformation($"Proxying GET request to: {path}");

            return await client.GetAsync(path);
        }

        public async Task<HttpResponseMessage> ProxyPostAsync(string path, object data, string accessToken)
        {
            using var client = CreateClient();
            AddAuthorizationHeader(client, accessToken);

            var json = JsonSerializer.Serialize(data);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            _logger.LogInformation($"Proxying POST request to: {path}");

            return await client.PostAsync(path, content);
        }

        public async Task<HttpResponseMessage> ProxyPutAsync(string path, object data, string accessToken)
        {
            using var client = CreateClient();
            AddAuthorizationHeader(client, accessToken);

            var json = JsonSerializer.Serialize(data);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            return await client.PutAsync(path, content);
        }

        public async Task<HttpResponseMessage> ProxyDeleteAsync(string path, string accessToken)
        {
            using var client = CreateClient();
            AddAuthorizationHeader(client, accessToken);

            return await client.DeleteAsync(path);
        }

        public async Task<Stream> ProxyDownloadAsync(string path, string accessToken)
        {
            using var client = CreateClient();
            AddAuthorizationHeader(client, accessToken);

            var response = await client.GetAsync(path);
            response.EnsureSuccessStatusCode();

            return await response.Content.ReadAsStreamAsync();
        }
    }
}
