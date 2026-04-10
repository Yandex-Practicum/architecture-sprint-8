namespace bionicpro_auth.Components.Handlers
{
    public interface IContextWrapper
    {

        void UpdateSessionCookie(HttpContext context, Guid sessionId);

    }
}
