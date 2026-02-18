import React from 'react';

interface LoginPageProps {
    onLogin: () => void;
}

const LoginPage: React.FC<LoginPageProps> = ({ onLogin }) => {
    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
            <div className="p-8 bg-white rounded-lg shadow-md text-center">
                <h1 className="text-3xl font-bold mb-4 text-gray-800">
                    BionicPRO Reports
                </h1>
                <p className="text-gray-600 mb-6">
                    Secure access to your prosthetics usage reports
                </p>
                <button
                    onClick={onLogin}
                    className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors font-medium"
                >
                    Sign In with Keycloak
                </button>
            </div>
        </div>
    );
};

export default LoginPage;
