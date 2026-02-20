import React from 'react';

interface LoginPageProps {
    onLogin: () => void;
    onLoginWithYandex: () => void;
}

const LoginPage: React.FC<LoginPageProps> = ({ onLogin, onLoginWithYandex }) => {
    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
            <div className="p-8 bg-white rounded-lg shadow-md text-center max-w-md w-full">
                <h1 className="text-3xl font-bold mb-4 text-gray-800">
                    BionicPRO Reports
                </h1>
                <p className="text-gray-600 mb-6">
                    Secure access to your prosthetics usage reports
                </p>
                
                <div className="space-y-3">
                    <button
                        onClick={onLogin}
                        className="w-full px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors font-medium"
                    >
                        Sign In with Keycloak
                    </button>
                    
                    <div className="flex items-center my-4">
                        <div className="flex-grow border-t border-gray-300"></div>
                        <span className="px-4 text-gray-500 text-sm">или</span>
                        <div className="flex-grow border-t border-gray-300"></div>
                    </div>
                    
                    <button
                        onClick={onLoginWithYandex}
                        className="w-full px-6 py-3 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors font-medium flex items-center justify-center gap-2"
                    >
                        <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12.9 2C9.4 2 6.5 4.2 5.8 7.2h3.2c.5-1.4 1.9-2.5 3.6-2.5 2.1 0 3.8 1.7 3.8 3.8 0 2.1-1.7 3.8-3.8 3.8h-.7v3.2h.7c2.1 0 3.8 1.7 3.8 3.8s-1.7 3.8-3.8 3.8c-1.7 0-3.1-1.1-3.6-2.5H5.8c.7 3 3.6 5.2 7.1 5.2 4 0 7.3-3.3 7.3-7.3 0-2.3-1.1-4.4-2.8-5.7 1.7-1.3 2.8-3.4 2.8-5.7 0-4-3.3-7.3-7.3-7.3z"/>
                        </svg>
                        Войти через Яндекс ID
                    </button>
                </div>
                
                <p className="text-xs text-gray-500 mt-6">
                    При входе через Яндекс ID, вы разрешаете использовать данные вашего профиля
                </p>
            </div>
        </div>
    );
};

export default LoginPage;
