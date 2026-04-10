namespace bionicpro_auth.Models
{
    public class SessionData
    {

        public Guid SessionId { get; set; }
        public UserInfo UserInfo { get; init; }

        public string AccessToken { get; init; }
        public string EncryptedRefreshToken { get; init; }
        public TimeSpan AccessTokenExpiry { get; init; }
        public TimeSpan RefreshTokenExpiry { get; init; }

        public DateTime SessionCreateAt { get; init; }
        public DateTime AccessTokenCreateAt { get; set; }

    }
}
