import axios from 'axios'

// 创建 axios 实例
const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    // 规范化错误信息，不显示消息，由组件决定如何处理
    const normalizedError = {
      status: 'error',
      message: error.response?.data?.detail
        || error.response?.data?.message
        || error.message
        || '请求失败',
      statusCode: error.response?.status,
      originalError: error
    }

    return Promise.reject(normalizedError)
  }
)

export default api