import axios from 'axios'

/**
 * Client for customer-facing pages (support widget, help center). It never
 * sends the agent's bearer token, and a 401 never triggers the shared client's
 * agent session refresh and login redirect.
 */
export const publicClient = axios.create({ baseURL: '/v1' })
