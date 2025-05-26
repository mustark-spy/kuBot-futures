#!/usr/bin/env python3
"""
Utilitaires pour le bot de trading
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class RiskManager:
    """Gestionnaire de risques pour le trading"""
    
    def __init__(self, max_drawdown: float = 0.1, max_daily_loss: float = 0.05):
        self.max_drawdown = max_drawdown  # 10% de drawdown maximum
        self.max_daily_loss = max_daily_loss  # 5% de perte journalière max
        self.daily_pnl = 0.0
        self.session_start_balance = 0.0
        self.peak_balance = 0.0
        
    def reset_daily_pnl(self):
        """Remet à zéro le PnL journalier"""
        self.daily_pnl = 0.0
        logger.info("PnL journalier remis à zéro")
    
    def update_pnl(self, pnl_change: float, current_balance: float):
        """Met à jour le PnL et vérifie les limites de risque"""
        self.daily_pnl += pnl_change
        
        # Mise à jour du pic de balance
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
        
        return self.check_risk_limits(current_balance)
    
    def check_risk_limits(self, current_balance: float) -> Dict[str, bool]:
        """Vérifie si les limites de risque sont dépassées"""
        risk_status = {
            'daily_limit_exceeded': False,
            'drawdown_limit_exceeded': False,
            'should_stop_trading': False
        }
        
        # Vérification perte journalière
        if self.session_start_balance > 0:
            daily_loss_pct = abs(self.daily_pnl) / self.session_start_balance
            if daily_loss_pct > self.max_daily_loss:
                risk_status['daily_limit_exceeded'] = True
                logger.warning(f"Limite de perte journalière dépassée: {daily_loss_pct:.2%}")
        
        # Vérification drawdown
        if self.peak_balance > 0:
            drawdown = (self.peak_balance - current_balance) / self.peak_balance
            if drawdown > self.max_drawdown:
                risk_status['drawdown_limit_exceeded'] = True
                logger.warning(f"Drawdown maximum dépassé: {drawdown:.2%}")
        
        # Décision d'arrêt
        risk_status['should_stop_trading'] = (
            risk_status['daily_limit_exceeded'] or 
            risk_status['drawdown_limit_exceeded']
        )
        
        return risk_status

class MarketAnalyzer:
    """Analyseur de marché pour conditions de trading"""
    
    @staticmethod
    def calculate_volatility(prices: List[float], period: int = 20) -> float:
        """Calcule la volatilité sur une période donnée"""
        if len(prices) < period:
            return 0.0
        
        returns = []
        for i in range(1, len(prices)):
            returns.append((prices[i] - prices[i-1]) / prices[i-1])
        
        if len(returns) < period:
            return np.std(returns) if returns else 0.0
        
        return np.std(returns[-period:])
    
    @staticmethod
    def detect_trend(prices: List[float], short_period: int = 10, long_period: int = 20) -> str:
        """Détecte la tendance du marché"""
        if len(prices) < long_period:
            return "insufficient_data"
        
        short_ma = sum(prices[-short_period:]) / short_period
        long_ma = sum(prices[-long_period:]) / long_period
        
        if short_ma > long_ma * 1.01:  # 1% au dessus
            return "bullish"
        elif short_ma < long_ma * 0.99:  # 1% en dessous
            return "bearish"
        else:
            return "sideways"
    
    @staticmethod
    def calculate_support_resistance(prices: List[float], window: int = 20) -> Tuple[float, float]:
        """Calcule les niveaux de support et résistance"""
        if len(prices) < window:
            min_price = min(prices) if prices else 0
            max_price = max(prices) if prices else 0
            return min_price, max_price
        
        recent_prices = prices[-window:]
        support = min(recent_prices)
        resistance = max(recent_prices)
        
        return support, resistance

class PerformanceTracker:
    """Suivi des performances du bot"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.trades_count = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        self.total_loss = 0.0
        self.max_consecutive_wins = 0
        self.max_consecutive_losses = 0
        self.current_streak = 0
        self.current_streak_type = None  # 'win' or 'loss'
        
    def add_trade(self, profit: float) -> Dict:
        """Ajoute un trade aux statistiques"""
        self.trades_count += 1
        
        if profit > 0:
            self.winning_trades += 1
            self.total_profit += profit
            self._update_streak('win')
        else:
            self.losing_trades += 1
            self.total_loss += abs(profit)
            self._update_streak('loss')
        
        return self.get_stats()
    
    def _update_streak(self, trade_type: str):
        """Met à jour les séries de gains/pertes"""
        if self.current_streak_type == trade_type:
            self.current_streak += 1
        else:
            self.current_streak = 1
            self.current_streak_type = trade_type
        
        if trade_type == 'win':
            self.max_consecutive_wins = max(self.max_consecutive_wins, self.current_streak)
        else:
            self.max_consecutive_losses = max(self.max_consecutive_losses, self.current_streak)
    
    def get_stats(self) -> Dict:
        """Retourne les statistiques de performance"""
        win_rate = (self.winning_trades / self.trades_count * 100) if self.trades_count > 0 else 0
        avg_win = self.total_profit / self.winning_trades if self.winning_trades > 0 else 0
        avg_loss = self.total_loss / self.losing_trades if self.losing_trades > 0 else 0
        profit_factor = self.total_profit / self.total_loss if self.total_loss > 0 else float('inf')
        
        runtime = datetime.now() - self.start_time
        
        return {
            'runtime_hours': runtime.total_seconds() / 3600,
            'total_trades': self.trades_count,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'total_pnl': self.total_profit - self.total_loss,
            'total_profit': self.total_profit,
            'total_loss': self.total_loss,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_consecutive_wins': self.max_consecutive_wins,
            'max_consecutive_losses': self.max_consecutive_losses,
            'current_streak': self.current_streak,
            'current_streak_type': self.current_streak_type
        }
    
    def get_performance_report(self) -> str:
        """Génère un rapport de performance formaté"""
        stats = self.get_stats()
        
        report = f"""
📊 **RAPPORT DE PERFORMANCE**

⏱️ **Durée**: {stats['runtime_hours']:.1f}h
📈 **Trades**: {stats['total_trades']} (🟢{stats['winning_trades']} | 🔴{stats['losing_trades']})
🎯 **Taux de réussite**: {stats['win_rate']:.1f}%

💰 **PnL Global**: {stats['total_pnl']:.4f} USDT
💹 **Profits**: +{stats['total_profit']:.4f} USDT
📉 **Pertes**: -{stats['total_loss']:.4f} USDT

📊 **Moyennes**:
   • Gain moyen: +{stats['avg_win']:.4f} USDT
   • Perte moyenne: -{stats['avg_loss']:.4f} USDT
   • Facteur de profit: {stats['profit_factor']:.2f}

🔥 **Séries**:
   • Max gains consécutifs: {stats['max_consecutive_wins']}
   • Max pertes consécutives: {stats['max_consecutive_losses']}
   • Série actuelle: {stats['current_streak']} {stats['current_streak_type'] or 'N/A'}
        """
        
        return report.strip()

class ConfigValidator:
    """Validateur de configuration"""
    
    @staticmethod
    def validate_config(config: Dict) -> Tuple[bool, List[str]]:
        """Valide la configuration du bot"""
        errors = []
        
        # Validation des clés API
        required_keys = [
            'KUCOIN_API_KEY', 'KUCOIN_API_SECRET', 'KUCOIN_API_PASSPHRASE',
            'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID'
        ]
        
        for key in required_keys:
            if not config.get(key):
                errors.append(f"Clé manquante ou vide: {key}")
        
        # Validation des paramètres numériques
        numeric_params = {
            'LEVERAGE': (1, 100),
            'GRID_SIZE': (2, 50),
            'BUDGET': (10, 1000000),
            'STOP_LOSS': (0.001, 0.1),
            'TAKE_PROFIT': (0.001, 0.2)
        }
        
        for param, (min_val, max_val) in numeric_params.items():
            value = config.get(param)
            if value is not None:
                try:
                    num_val = float(value)
                    if not (min_val <= num_val <= max_val):
                        errors.append(f"{param} hors limites: {num_val} (doit être entre {min_val} et {max_val})")
                except ValueError:
                    errors.append(f"{param} doit être un nombre: {value}")
        
        # Validation du symbole
        symbol = config.get('SYMBOL', '')
        if symbol and not symbol.replace('-', '').replace(':', '').isalnum():
            errors.append(f"Format de symbole invalide: {symbol}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def get_safe_config(config: Dict) -> Dict:
        """Retourne une configuration sécurisée (sans clés sensibles)"""
        safe_config = config.copy()
        sensitive_keys = [
            'KUCOIN_API_KEY', 'KUCOIN_API_SECRET', 'KUCOIN_API_PASSPHRASE',
            'TELEGRAM_TOKEN'
        ]
        
        for key in sensitive_keys:
            if key in safe_config:
                safe_config[key] = '***MASKED***'
        
        return safe_config

class OrderManager:
    """Gestionnaire d'ordres pour optimiser les performances"""
    
    def __init__(self):
        self.pending_orders = {}
        self.filled_orders = {}
        self.cancelled_orders = {}
        
    def add_pending_order(self, order_id: str, order_data: Dict):
        """Ajoute un ordre en attente"""
        self.pending_orders[order_id] = {
            **order_data,
            'created_at': datetime.now(),
            'status': 'pending'
        }
        logger.info(f"Ordre ajouté en attente: {order_id}")
    
    def mark_filled(self, order_id: str, fill_data: Dict):
        """Marque un ordre comme rempli"""
        if order_id in self.pending_orders:
            order = self.pending_orders.pop(order_id)
            self.filled_orders[order_id] = {
                **order,
                **fill_data,
                'filled_at': datetime.now(),
                'status': 'filled'
            }
            logger.info(f"Ordre marqué comme rempli: {order_id}")
            return order
        return None
    
    def mark_cancelled(self, order_id: str):
        """Marque un ordre comme annulé"""
        if order_id in self.pending_orders:
            order = self.pending_orders.pop(order_id)
            self.cancelled_orders[order_id] = {
                **order,
                'cancelled_at': datetime.now(),
                'status': 'cancelled'
            }
            logger.info(f"Ordre marqué comme annulé: {order_id}")
            return order
        return None
    
    def get_pending_count(self) -> int:
        """Retourne le nombre d'ordres en attente"""
        return len(self.pending_orders)
    
    def get_filled_count(self) -> int:
        """Retourne le nombre d'ordres remplis"""
        return len(self.filled_orders)
    
    def cleanup_old_orders(self, hours: int = 24):
        """Nettoie les anciens ordres remplis/annulés"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Nettoyage des ordres remplis anciens
        old_filled = [
            order_id for order_id, order in self.filled_orders.items()
            if order.get('filled_at', datetime.now()) < cutoff_time
        ]
        for order_id in old_filled:
            del self.filled_orders[order_id]
        
        # Nettoyage des ordres annulés anciens
        old_cancelled = [
            order_id for order_id, order in self.cancelled_orders.items()
            if order.get('cancelled_at', datetime.now()) < cutoff_time
        ]
        for order_id in old_cancelled:
            del self.cancelled_orders[order_id]
        
        if old_filled or old_cancelled:
            logger.info(f"Nettoyage: {len(old_filled)} ordres remplis, {len(old_cancelled)} ordres annulés supprimés")

class NotificationFormatter:
    """Formateur de notifications pour Telegram"""
    
    @staticmethod
    def format_startup_message(config: Dict) -> str:
        """Formate le message de démarrage"""
        safe_config = ConfigValidator.get_safe_config(config)
        
        return f"""
🚀 <b>BOT DE TRADING DÉMARRÉ</b>

⚙️ <b>Configuration:</b>
• Symbol: {safe_config.get('SYMBOL', 'N/A')}
• Budget: {safe_config.get('BUDGET', 'N/A')} USDT
• Levier: {safe_config.get('LEVERAGE', 'N/A')}x
• Taille grille: {safe_config.get('GRID_SIZE', 'N/A')}
• Stop Loss: {float(safe_config.get('STOP_LOSS', 0)) * 100:.1f}%
• Take Profit: {float(safe_config.get('TAKE_PROFIT', 0)) * 100:.1f}%
• Ajustement ATR: {safe_config.get('ADJUST_INTERVAL_MIN', 'N/A')} min
• Mode: {'🧪 SANDBOX' if safe_config.get('SANDBOX') == 'true' else '💰 PRODUCTION'}

🎯 <b>Stratégie:</b> Grille Adaptative ATR
        """.strip()
    
    @staticmethod
    def format_grid_setup(grid_data: Dict) -> str:
        """Formate le message de configuration de grille"""
        return f"""
⚙️ <b>GRILLE CONFIGURÉE</b>

📊 <b>Paramètres ATR:</b>
• ATR: {grid_data.get('atr', 0):.4f}
• Prix actuel: {grid_data.get('current_price', 0):.2f}

📏 <b>Bornes de grille:</b>
• Borne inférieure: {grid_data.get('lower_bound', 0):.2f}
• Borne supérieure: {grid_data.get('upper_bound', 0):.2f}
• Spread: {grid_data.get('spread', 0):.4f}
• Increment: {grid_data.get('increment', 0):.6f}

📋 <b>Couverture:</b>
• Nombre d'ordres: {grid_data.get('total_orders', 0)}
• Ordres d'achat: {grid_data.get('buy_orders', 0)}
• Ordres de vente: {grid_data.get('sell_orders', 0)}
        """.strip()
    
    @staticmethod
    def format_order_filled(order_data: Dict, mirror_data: Dict, profit: float) -> str:
        """Formate le message d'ordre rempli"""
        return f"""
✅ <b>ORDRE REMPLI & MIROIR CRÉÉ</b>

📋 <b>Ordre rempli:</b>
• Type: {order_data.get('side', '').upper()}
• Quantité: {order_data.get('size', 0):.6f}
• Prix: {order_data.get('price', 0):.2f}

🪞 <b>Ordre miroir:</b>
• Type: {mirror_data.get('side', '').upper()}
• Quantité: {mirror_data.get('size', 0):.6f}
• Prix: {mirror_data.get('price', 0):.2f}

💰 <b>Profit estimé:</b> +{profit:.4f} USDT
        """.strip()
    
    @staticmethod
    def format_grid_adjustment(old_bounds: Tuple[float, float], new_bounds: Tuple[float, float]) -> str:
        """Formate le message d'ajustement de grille"""
        return f"""
🔄 <b>GRILLE AJUSTÉE</b>

📊 <b>Anciennes bornes:</b>
• {old_bounds[0]:.2f} - {old_bounds[1]:.2f}

📊 <b>Nouvelles bornes:</b>
• {new_bounds[0]:.2f} - {new_bounds[1]:.2f}

🎯 Ajustement basé sur la volatilité ATR
        """.strip()
    
    @staticmethod
    def format_risk_alert(risk_data: Dict) -> str:
        """Formate l'alerte de risque"""
        alert_type = "⚠️ ALERTE RISQUE"
        if risk_data.get('should_stop_trading'):
            alert_type = "🛑 ARRÊT TRADING"
        
        message = f"{alert_type}\n\n"
        
        if risk_data.get('daily_limit_exceeded'):
            message += f"📉 Limite journalière dépassée\n"
        
        if risk_data.get('drawdown_limit_exceeded'):
            message += f"📊 Drawdown maximum dépassé\n"
        
        message += f"\n🔒 Trading {'SUSPENDU' if risk_data.get('should_stop_trading') else 'SURVEILLÉ'}"
        
        return message

class FileUtils:
    """Utilitaires pour la gestion des fichiers"""
    
    @staticmethod
    def ensure_directory(path: str):
        """S'assure que le répertoire existe"""
        import os
        os.makedirs(path, exist_ok=True)
        logger.info(f"Répertoire créé/vérifié: {path}")
    
    @staticmethod
    def backup_file(filepath: str, backup_dir: str = None):
        """Crée une sauvegarde d'un fichier"""
        import os
        import shutil
        
        if not os.path.exists(filepath):
            return False
        
        if backup_dir is None:
            backup_dir = os.path.dirname(filepath)
        
        FileUtils.ensure_directory(backup_dir)
        
        filename = os.path.basename(filepath)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{timestamp}_{filename}"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        try:
            shutil.copy2(filepath, backup_path)
            logger.info(f"Sauvegarde créée: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Erreur création sauvegarde: {e}")
            return False
    
    @staticmethod
    def cleanup_old_files(directory: str, pattern: str, max_age_days: int = 7):
        """Nettoie les anciens fichiers selon un pattern"""
        import os
        import glob
        
        if not os.path.exists(directory):
            return
        
        pattern_path = os.path.join(directory, pattern)
        files = glob.glob(pattern_path)
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        
        deleted_count = 0
        for file_path in files:
            try:
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_time < cutoff_time:
                    os.remove(file_path)
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Erreur suppression fichier {file_path}: {e}")
        
        if deleted_count > 0:
            logger.info(f"Nettoyage: {deleted_count} fichiers supprimés dans {directory}")

class MathUtils:
    """Utilitaires mathématiques pour le trading"""
    
    @staticmethod
    def calculate_position_size(budget: float, price: float, leverage: int, risk_percent: float = 0.02) -> float:
        """Calcule la taille de position optimale"""
        # Taille de position basée sur le risque
        risk_amount = budget * risk_percent
        position_value = risk_amount * leverage
        position_size = position_value / price
        
        return round(position_size, 8)
    
    @staticmethod
    def calculate_optimal_grid_spacing(price_range: float, volatility: float, grid_size: int) -> float:
        """Calcule l'espacement optimal de la grille"""
        # Espacement basé sur la volatilité et la range de prix
        base_spacing = price_range / grid_size
        volatility_factor = max(0.5, min(2.0, volatility * 10))  # Facteur entre 0.5 et 2.0
        
        optimal_spacing = base_spacing * volatility_factor
        return round(optimal_spacing, 8)
    
    @staticmethod
    def calculate_take_profit_distance(atr: float, multiplier: float = 2.0) -> float:
        """Calcule la distance de take profit basée sur l'ATR"""
        return atr * multiplier
    
    @staticmethod
    def calculate_stop_loss_distance(atr: float, multiplier: float = 1.5) -> float:
        """Calcule la distance de stop loss basée sur l'ATR"""
        return atr * multiplier
    
    @staticmethod
    def normalize_price(price: float, tick_size: float = 0.01) -> float:
        """Normalise un prix selon la taille de tick"""
        return round(price / tick_size) * tick_size
    
    @staticmethod
    def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """Calcule le ratio de Sharpe"""
        if not returns or len(returns) < 2:
            return 0.0
        
        excess_returns = [r - risk_free_rate for r in returns]
        mean_return = np.mean(excess_returns)
        std_return = np.std(excess_returns)
        
        if std_return == 0:
            return 0.0
        
        return mean_return / std_return

def setup_logging(log_level: str = "INFO", log_file: str = "bot.log"):
    """Configure le système de logging"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Niveau de log invalide: {log_level}')
    
    # Format des logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Handler pour fichier
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    
    # Handler pour console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    
    # Configuration du logger principal
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    logger.info(f"Logging configuré - Niveau: {log_level}, Fichier: {log_file}")

def format_number(number: float, decimals: int = 4) -> str:
    """Formate un nombre pour l'affichage"""
    if abs(number) >= 1000000:
        return f"{number/1000000:.{decimals-2}f}M"
    elif abs(number) >= 1000:
        return f"{number/1000:.{decimals-1}f}K"
    else:
        return f"{number:.{decimals}f}"

def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """Calcule le pourcentage de changement"""
    if old_value == 0:
        return 0.0
    return ((new_value - old_value) / old_value) * 100