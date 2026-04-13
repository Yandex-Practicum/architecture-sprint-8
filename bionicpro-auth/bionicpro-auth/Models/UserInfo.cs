namespace bionicpro_auth.Models
{
    public record UserInfo
    {
        public string Sub { get; set; } = string.Empty;
        public string PreferredUsername { get; set; } = string.Empty;
        public string Email { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;

    }
}
