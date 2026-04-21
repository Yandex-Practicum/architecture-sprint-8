namespace bionicpro_auth.Components.Handlers
{
    public interface IEncryptor
    {

        string Encrypt(string secret);
        string Decrypt(string encodedSecret);

    }
}
