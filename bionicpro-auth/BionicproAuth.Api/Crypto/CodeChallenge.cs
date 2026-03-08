using System.Security.Cryptography;
using System.Text;

namespace BionicproAuth.Api.Crypto;

public static class CodeChallenge
{
    public static string GenerateCodeChallenge(string codeVerifier, string codeChallengeMethod)
    {
        if (codeChallengeMethod == "plain")
        {
            return codeVerifier;
        }
        else if (codeChallengeMethod == "S256")
        {
            using var sha256 = SHA256.Create();
            var bytes = Encoding.ASCII.GetBytes(codeVerifier);
            var hash = sha256.ComputeHash(bytes);
            return Base64UrlEncode(hash);
        }
    
        throw new NotSupportedException($"Method {codeChallengeMethod} is not supported.");
    }

    
    private static string Base64UrlEncode(byte[] bytes)
    {
        string base64 = Convert.ToBase64String(bytes);
        return base64.Replace('+', '-').Replace('/', '_').TrimEnd('=');
    }
}
