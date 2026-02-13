// Updated to work with cookie-based authentication
export function getAuthHeaders() {
    // No authorization headers needed with cookie authentication
    return {};
}

export async function securedFetch(url, options = {}) {
    // Include credentials to send cookies with the request
    const response = await fetch(url, { 
        ...options, 
        headers: { ...getAuthHeaders(), ...options.headers },
        credentials: 'include' // This is important for including cookies in requests
    });
    
    return response;
}

export async function checkAuthentication() {
    try {
        // Make a request to an endpoint that verifies the auth cookie
        const response = await securedFetch('/api/v1/auth/check');
        if (!response.ok) {
            return false;
        }
        
        const data = await response.json();
        return data.authenticated;
    } catch (error) {
        console.error('Authentication check failed:', error);
        return false;
    }
}
