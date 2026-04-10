namespace bionicpro_auth.Models
{
    public record UserInfo
    {
        public string UserId { get; init; }
        public string? Name { get; init; }
        public string UserName { get; init; }

    }
}
