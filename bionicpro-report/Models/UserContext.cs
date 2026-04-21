namespace bionicpro_report.Models
{
    public class UserContext
    {
        public string UserId { get; set; } = string.Empty;
        public string UserName { get; set; } = string.Empty;
        public string Email { get; set; } = string.Empty;
        public List<string> ProsthesisIds { get; set; } = new();
        public List<string> Roles { get; set; } = new();
    }
}
