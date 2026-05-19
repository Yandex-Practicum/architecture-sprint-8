namespace bionicpro_auth.models
{
    /// <summary>
    /// Ответ на запрос логина пользователя
    /// </summary>
    /// <param name="AccessToken"> Access токен </param>
    /// <param name="RefreshToken"> Refresh токен </param>
    internal record AuthResponse(string AccessToken, string RefreshToken);
}