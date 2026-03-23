using System.Security.Cryptography;

namespace BionicproAuth.Api.Crypto;

public static class CryptoRandom
{
    public static string CreateUniqueId(int length = 32)
    {
        // Генерируем криптостойкие случайные байты
        byte[] bytes = new byte[length];
        RandomNumberGenerator.Fill(bytes);
        
        // Конвертируем в Base64Url (без '+', '/' и '=')
        return Base64UrlEncode(bytes);
    }

    private static string Base64UrlEncode(byte[] bytes)
    {
        string base64 = Convert.ToBase64String(bytes);
        // Преобразование Base64 в Base64Url
        return base64.Replace('+', '-').Replace('/', '_').TrimEnd('=');
    }
}