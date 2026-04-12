namespace bionicpro_auth.Models.Rest
{
    public record LoginRequest
    {
        public string UserName { get; set; }
        public string Pass { get; set; }
        public string? Otp { get; set; }
    }
}
