namespace bionicpro_auth.Models
{
    public record TokensInfo
    {

        public required string AccessToken { get; set; }
        public required string RefreshToken { get; set; }
        public required int ExpiredIn { get; set; }
        public required string TokenType { get; set; }

    }
}
