namespace BionicproAuth.Api.Session;

public interface ITokenExchangeService
{
    Task<string> ExchangeUserTokenAsync(string userAccessToken);
}