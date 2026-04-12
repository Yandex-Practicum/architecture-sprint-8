namespace bionicpro_auth.Models
{
    public class AuthResult
    {
        public bool IsSuccess { get; set; }

        public bool RequiresOtp { get; set; }

        public string? ErrorMessage { get; set; }

        public KeycloakTokenResponse? Tokens { get; set; }

    }
}
