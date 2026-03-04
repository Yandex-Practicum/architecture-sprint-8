
export const UserCard = ({ userinfo }) => {

    const login = () => {
        window.location.replace(`${process.env.REACT_APP_AUTH_URL}/auth/login`);
    };

    const logout = () => {
        window.location.replace(`${process.env.REACT_APP_AUTH_URL}/auth/logout`);
    };

    const downloadReport = async () => {
        const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
            credentials: "include"
        });
        response.json().then(data => downloadJSON(data))
        if (response.status === 401) {
            login();
            return;
        }
    };

    const downloadJSON = (data) => {
        const jsonString = JSON.stringify(data, null, 2);

        const blob = new Blob([jsonString], { type: 'application/json' });

        const url = URL.createObjectURL(blob);

        const link = document.createElement('a');
        link.href = url;
        link.download = 'report.json';

        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        URL.revokeObjectURL(url);
    };

    return (
        <section class="vh-100">
            <div class="container py-5 h-100">
                <div class="row d-flex justify-content-center align-items-center h-100">
                    <div class="col-md-12 col-xl-4">
                        <div class="card" style={{ borderRadius: "15px" }}>
                            <div class="card-body text-center">
                                <div class="mt-3 mb-4 d-flex justify-content-center">
                                    <img
                                        src="https://mdbcdn.b-cdn.net/img/Photos/new-templates/bootstrap-chat/ava6-bg.webp"
                                        class="rounded-circle img-fluid"
                                        style={{ width: "100px" }}
                                    />
                                </div>
                                <h4 class="mb-2">{userinfo.firstName} {userinfo.lastName}</h4>
                                <p class="text-muted mb-4 text-center">{userinfo.email}</p>

                                <div class="d-flex gap-2 justify-content-center mb-4 pb-2">
                                    <button
                                        type="button"
                                        onClick={downloadReport}
                                        class="btn btn-primary btn-rounded btn-lg"
                                    >
                                        Download report
                                    </button>
                                    <button
                                        type="button"
                                        onClick={logout}
                                        class="btn btn-outline-danger btn-rounded btn-lg"
                                    >
                                        Logout
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    )
}