"""
Health check endpoint para Render
Render usa este endpoint para verificar que la aplicación está funcionando
"""
from flask import jsonify

def register_health_check(app):
    """Registra el endpoint de health check"""
    @app.route('/health', methods=['GET'])
    def health_check():
        """Endpoint simple para health check de Render"""
        return jsonify({
            'status': 'ok',
            'service': 'aspers-web-app'
        }), 200
    
    @app.route('/healthz', methods=['GET'])
    def health_check_z():
        """Endpoint alternativo para health check"""
        return jsonify({
            'status': 'ok',
            'service': 'aspers-web-app'
        }), 200

