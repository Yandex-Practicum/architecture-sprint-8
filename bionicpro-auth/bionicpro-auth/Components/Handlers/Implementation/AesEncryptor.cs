using bionicpro_auth.Components.Handlers;
using Microsoft.AspNetCore.DataProtection.KeyManagement;
using System.Security.Cryptography;
using System.Text;

namespace bionicpro_auth.Components.Handlers.Implementation
{
    public class AesEncryptor : IEncryptor
    {
        private byte[] _key;
        private byte[] _iv = Encoding.UTF8.GetBytes(Guid.NewGuid().ToString("N"));


        public static AesEncryptor Init()
        {
            AesEncryptor encryptor = new();

            encryptor._key = new byte[32]; // 256 bits
            encryptor._iv = new byte[16]; // 128 bits

            using var rng = RandomNumberGenerator.Create();
            rng.GetBytes(encryptor._key);
            rng.GetBytes(encryptor._iv);

            return encryptor;
        }

        public string Encrypt(string secret)
        {
            using (Aes aesAlg = Aes.Create())
            {
                aesAlg.Key = _key;
                aesAlg.IV = _iv;

                // Create an encryptor to perform the stream transform
                ICryptoTransform encryptor = aesAlg.CreateEncryptor(aesAlg.Key, aesAlg.IV);

                // Create the streams used for encryption
                using (MemoryStream msEncrypt = new MemoryStream())
                {
                    using (CryptoStream csEncrypt = new CryptoStream(msEncrypt, encryptor, CryptoStreamMode.Write))
                    {
                        using (StreamWriter swEncrypt = new StreamWriter(csEncrypt))
                        {
                            // Write all data to the stream
                            swEncrypt.Write(secret);
                        }
                    }

                    return Convert.ToBase64String(msEncrypt.ToArray());
                }
            }

        }

        public string Decrypt(string encodedSecret)
        {
            byte[] dataEncyptedString = Convert.FromBase64String(encodedSecret);
            using (Aes aesAlg = Aes.Create())
            {
                aesAlg.Key = _key;
                aesAlg.IV = _iv;

                // Create a decryptor to perform the stream transform
                ICryptoTransform decryptor = aesAlg.CreateDecryptor(aesAlg.Key, aesAlg.IV);

                // Create the streams used for decryption
                using (MemoryStream msDecrypt = new MemoryStream(dataEncyptedString))
                {
                    using (CryptoStream csDecrypt = new CryptoStream(msDecrypt, decryptor, CryptoStreamMode.Read))
                    {
                        using (StreamReader srDecrypt = new StreamReader(csDecrypt))
                        {
                            // Read the decrypted bytes from the decrypting stream
                            return srDecrypt.ReadToEnd();
                        }
                    }
                }
            }

        }
    }
}
