package http

const (
	authorizationHeader   = "Authorization"
	prefixTokenBearer     = "Bearer "
	protheticUserRoleName = "prothetic_user"
)

type ErrorMessage struct {
	Error string `json:"error"`
}
