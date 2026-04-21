namespace bionicpro_auth.Models.Settings
{
    public class SessionSettings
    {

        public TimeSpan SessionLifeTime { get; init; } = TimeSpan.FromHours(1);

        public string CookiesName { get; init; } = "bionicpro_cookie";

    }
}
