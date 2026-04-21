namespace bionicpro_auth.Components.Handlers
{
    public interface IReportsProxyService
    {
        Task<HttpResponseMessage> ProxyGetAsync(string path, string accessToken);
        Task<HttpResponseMessage> ProxyPostAsync(string path, object data, string accessToken);
        Task<HttpResponseMessage> ProxyPutAsync(string path, object data, string accessToken);
        Task<HttpResponseMessage> ProxyDeleteAsync(string path, string accessToken);
        Task<Stream> ProxyDownloadAsync(string path, string accessToken);
    }
}
