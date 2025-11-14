"""
Settings routes for risk categories management
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.repositories import risk_categories_repository
from app.utils.security import require_action
import logging

bp = Blueprint('settings', __name__, url_prefix='/settings')
logger = logging.getLogger(__name__)


@bp.route('/risk-categories')
@login_required
@require_action('edit')
def risk_categories():
    """List all risk categories"""
    try:
        categories = risk_categories_repository.list_all_categories()
        return render_template('settings/risk_categories.html', categories=categories)
    except Exception as e:
        logger.error(f'Error listing risk categories: {str(e)}', exc_info=True)
        flash(f'Erro ao listar categorias: {str(e)}', 'error')
        return redirect(url_for('reviews.dashboard'))


@bp.route('/risk-categories/new', methods=['POST'])
@login_required
@require_action('edit')
def create_risk_category():
    """Create a new risk category"""
    try:
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('Nome da categoria é obrigatório', 'error')
            return redirect(url_for('settings.risk_categories'))
        
        category_id = risk_categories_repository.create_category(
            name, description, current_user.email
        )
        
        if category_id:
            flash(f'Categoria "{name}" criada com sucesso!', 'success')
        else:
            flash('Erro ao criar categoria', 'error')
            
    except Exception as e:
        logger.error(f'Error creating risk category: {str(e)}', exc_info=True)
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            flash(f'Já existe uma categoria com o nome "{name}"', 'error')
        else:
            flash(f'Erro ao criar categoria: {str(e)}', 'error')
    
    return redirect(url_for('settings.risk_categories'))


@bp.route('/risk-categories/<int:category_id>/edit', methods=['POST'])
@login_required
@require_action('edit')
def edit_risk_category(category_id):
    """Edit an existing risk category"""
    try:
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('Nome da categoria é obrigatório', 'error')
            return redirect(url_for('settings.risk_categories'))
        
        success = risk_categories_repository.update_category(
            category_id, name, description
        )
        
        if success:
            flash(f'Categoria "{name}" atualizada com sucesso!', 'success')
        else:
            flash('Categoria não encontrada', 'error')
            
    except Exception as e:
        logger.error(f'Error updating risk category: {str(e)}', exc_info=True)
        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
            flash(f'Já existe uma categoria com o nome "{name}"', 'error')
        else:
            flash(f'Erro ao atualizar categoria: {str(e)}', 'error')
    
    return redirect(url_for('settings.risk_categories'))


@bp.route('/risk-categories/<int:category_id>/delete', methods=['POST'])
@login_required
@require_action('edit')
def delete_risk_category(category_id):
    """Delete a risk category permanently (hard delete)"""
    try:
        # Get category info before deleting
        category = risk_categories_repository.get_category_by_id(category_id)
        
        if not category:
            flash('Categoria não encontrada', 'error')
            return redirect(url_for('settings.risk_categories'))
        
        # Check if category is in use
        usage_info = risk_categories_repository.check_category_in_use(category_id)
        
        # Delete category (hard delete)
        success = risk_categories_repository.delete_category(category_id)
        
        if success:
            if usage_info['total_risks'] > 0:
                flash(
                    f'Categoria "{category["name"]}" excluída com sucesso! '
                    f'{usage_info["total_risks"]} risco(s) associado(s) agora estão sem categoria.',
                    'warning'
                )
            else:
                flash(f'Categoria "{category["name"]}" excluída com sucesso!', 'success')
        else:
            flash('Erro ao excluir categoria', 'error')
            
    except Exception as e:
        logger.error(f'Error deleting risk category: {str(e)}', exc_info=True)
        flash(f'Erro ao excluir categoria: {str(e)}', 'error')
    
    return redirect(url_for('settings.risk_categories'))


@bp.route('/risk-categories/<int:category_id>/usage')
@login_required
@require_action('view')
def check_category_usage(category_id):
    """Check if a category is being used (AJAX endpoint)"""
    try:
        usage_info = risk_categories_repository.check_category_in_use(category_id)
        return jsonify({
            'success': True,
            'total_risks': usage_info['total_risks'],
            'risk_ids': usage_info['risk_ids']
        })
    except Exception as e:
        logger.error(f'Error checking category usage: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

