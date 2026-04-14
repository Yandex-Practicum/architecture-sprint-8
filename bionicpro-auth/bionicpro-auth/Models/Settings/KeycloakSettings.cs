namespace bionicpro_auth.Models.Settings
{
    public class KeycloakSettings
    {


        public string BaseUrl4Front { get; set; }
        public string BaseUrl4Back { get; set; }

        public string Realm { get; set; }
        public KCCredentional BackendCredentional { get; set; }
        public KCCredentional FrontendCredentional { get; set; }
    }
}
