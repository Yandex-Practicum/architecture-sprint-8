namespace bionicpro_auth.Models.Rest
{
    public record LoginRequest
    {
        public required string UserName { get; set; }
        public required string Pass { get; set; }
    }
}
