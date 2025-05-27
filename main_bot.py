#!/usr/bin/env python3
"""
Bot de Trading Telegram avec Stratégie de Grille Adaptative
Plateforme: KuCoin Futures
Auteur: Assistant Claude
"""

import asyncio
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from kucoin_universal_sdk.api import DefaultClient
from kucoin_universal_sdk.client_parameter import ClientParameter
import websockets
from dataclasses import dataclass, asdict
import signal
import sys

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class GridConfig:
    """Configuration de la grille"""
    symbol: str
    leverage: int
    grid_size: int
    budget: float
    upper_bound: float
    lower_bound: float
    spread: float
    increment: float
    stop_loss: float
    take_profit: float
    atr_period: int = 14

@dataclass
class Order:
    """Représentation d'un ordre"""
    order_id: str
    symbol: str
    side: str  # 'buy' ou 'sell'
    size: float
    price: float
    status: str
    created_at: datetime
    filled_at: Optional[datetime] = None

class DataPersistence:
    """Gestion de la persistance des données"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
    def save_orders(self, orders: List[Order]):
        """Sauvegarde les ordres"""
        orders_data = [asdict(order) for order in orders]
        for order_data in orders_data:
            if 'created_at' in order_data and isinstance(order_data['created_at'], datetime):
                order_data['created_at'] = order_data['created_at'].isoformat()
            if 'filled_at' in order_data and order_data['filled_at']:
                if isinstance(order_data['filled_at'], datetime):
                    order_data['filled_at'] = order_data['filled_at'].isoformat()
        
        with open(os.path.join(self.data_dir, 'orders.json'), 'w') as f:
            json.dump(orders_data, f, indent=2)
    
    def load_orders(self) -> List[Order]:
        """Charge les ordres sauvegardés"""
        try:
            with open(os.path.join(self.data_dir, 'orders.json'), 'r') as f:
                orders_data = json.load(f)
            
            orders = []
            for order_data in orders_data:
                if 'created_at' in order_data:
                    order_data['created_at'] = datetime.fromisoformat(order_data['created_at'])
                if 'filled_at' in order_data and order_data['filled_at']:
                    order_data['filled_at'] = datetime.fromisoformat(order_data['filled_at'])
                orders.append(Order(**order_data))
            
            return orders
        except FileNotFoundError:
            return []
    
    def save_pnl(self, pnl_data: Dict):
        """Sauvegarde les données PnL"""
        with open(os.path.join(self.data_dir, 'pnl.json'), 'w') as f:
            json.dump(pnl_data, f, indent=2)
    
    def load_pnl(self) -> Dict:
        """Charge les données PnL"""
        try:
            with open(os.path.join(self.data_dir, 'pnl.json'), 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {'total_pnl': 0, 'trades': []}

class ATRCalculator:
    """Calculateur d'ATR (Average True Range)"""
    
    @staticmethod
    def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        """Calcule l'ATR"""
        if len(highs) < period + 1:
            return 0
        
        true_ranges = []
        for i in range(1, len(highs)):
            high_low = highs[i] - lows[i]
            high_close_prev = abs(highs[i] - closes[i-1])
            low_close_prev = abs(lows[i] - closes[i-1])
            true_range = max(high_low, high_close_prev, low_close_prev)
            true_ranges.append(true_range)
        
        if len(true_ranges) < period:
            return sum(true_ranges) / len(true_ranges)
        
        # ATR = moyenne mobile simple des true ranges
        return sum(true_ranges[-period:]) / period

class GridTradingBot:
    """Bot de trading avec stratégie de grille adaptative"""
    
    def __init__(self):
        self.load_config()
        self.kucoin_client = DefaultClient(
    ClientParameter(
        api_key=os.getenv("KUCOIN_API_KEY"),
        api_secret=os.getenv("KUCOIN_API_SECRET"),
        passphrase=os.getenv("KUCOIN_API_PASSPHRASE"),
        is_sandbox=os.getenv("SANDBOX", "true").lower() == "true"
    )
)
        self.telegram_bot = Bot(token=self.telegram_token)
        self.persistence = DataPersistence(self.data_dir)
        
        self.active_orders: List[Order] = []
        self.grid_config: Optional[GridConfig] = None
        self.last_atr_update = datetime.now()
        self.current_price = 0.0
        self.running = False
        
    def load_config(self):
        """Charge la configuration depuis les variables d'environnement"""
        self.api_key = os.getenv('KUCOIN_API_KEY')
        self.api_secret = os.getenv('KUCOIN_API_SECRET')
        self.api_passphrase = os.getenv('KUCOIN_API_PASSPHRASE')
        self.telegram_token = os.getenv('TELEGRAM_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        self.symbol = os.getenv('SYMBOL', 'BTC-USDT')
        self.leverage = int(os.getenv('LEVERAGE', '10'))
        self.grid_size = int(os.getenv('GRID_SIZE', '10'))
        self.adjust_interval = int(os.getenv('ADJUST_INTERVAL_MIN', '15'))
        self.stop_loss = float(os.getenv('STOP_LOSS', '0.01'))
        self.take_profit = float(os.getenv('TAKE_PROFIT', '0.02'))
        self.budget = float(os.getenv('BUDGET', '1000'))
        self.data_dir = os.getenv('DATA_DIR', './data')
        self.sandbox = os.getenv('SANDBOX', 'true').lower() == 'true'
        
        logger.info(f"Configuration chargée - Symbol: {self.symbol}, Budget: {self.budget}, Sandbox: {self.sandbox}")
    
    async def send_telegram_message(self, message: str):
        """Envoie un message Telegram"""
        try:
            await self.telegram_bot.send_message(
                chat_id=self.telegram_chat_id,
                text=message,
                parse_mode='HTML'
            )
            logger.info(f"Message Telegram envoyé: {message[:50]}...")
        except Exception as e:
            logger.error(f"Erreur envoi Telegram: {e}")
    
    async def get_current_price(self) -> float:
        """Récupère le prix actuel"""
        try:
            response = self.kucoin_client.get_ticker(self.symbol)
            if response and 'data' in response:
                price = float(response['data']['price'])
                logger.info(f"Prix actuel {self.symbol}: {price}")
                return price
            return 0.0
        except Exception as e:
            logger.error(f"Erreur récupération prix: {e}")
            return 0.0
    
    async def get_klines(self, period: str = '1hour', limit: int = 100) -> List[Dict]:
        """Récupère les données de chandelier"""
        try:
            response = self.kucoin_client.get_kline(
                symbol=self.symbol,
                type=period,
                startAt=int((datetime.now() - timedelta(hours=limit)).timestamp()),
                endAt=int(datetime.now().timestamp())
            )
            if response and 'data' in response:
                return response['data']
            return []
        except Exception as e:
            logger.error(f"Erreur récupération klines: {e}")
            return []
    
    async def calculate_atr_bounds(self) -> Tuple[float, float]:
        """Calcule les bornes de la grille basées sur l'ATR"""
        try:
            klines = await self.get_klines(period='1hour', limit=50)
            if not klines:
                logger.warning("Aucune donnée de chandelier disponible")
                current_price = await self.get_current_price()
                return current_price * 0.95, current_price * 1.05
            
            highs = [float(kline[2]) for kline in klines]
            lows = [float(kline[3]) for kline in klines]
            closes = [float(kline[4]) for kline in klines]
            
            atr = ATRCalculator.calculate_atr(highs, lows, closes)
            current_price = await self.get_current_price()
            
            # Utilisation de l'ATR pour définir les bornes
            atr_multiplier = 2.0  # Facteur d'ajustement
            lower_bound = current_price - (atr * atr_multiplier)
            upper_bound = current_price + (atr * atr_multiplier)
            
            logger.info(f"ATR calculé: {atr:.4f}, Bornes: {lower_bound:.2f} - {upper_bound:.2f}")
            await self.send_telegram_message(
                f"📊 <b>ATR Update</b>\n"
                f"ATR: {atr:.4f}\n"
                f"Prix actuel: {current_price:.2f}\n"
                f"Borne inférieure: {lower_bound:.2f}\n"
                f"Borne supérieure: {upper_bound:.2f}"
            )
            
            return lower_bound, upper_bound
            
        except Exception as e:
            logger.error(f"Erreur calcul ATR: {e}")
            current_price = await self.get_current_price()
            return current_price * 0.95, current_price * 1.05
    
    def calculate_grid_parameters(self, lower_bound: float, upper_bound: float) -> Tuple[float, float]:
        """Calcule les paramètres de la grille"""
        price_range = upper_bound - lower_bound
        spread = price_range / self.grid_size
        
        # Calcul de l'increment basé sur le budget et la taille de grille
        position_size = self.budget / (self.grid_size * 2)  # Division par 2 car buy et sell
        increment = position_size / lower_bound  # Taille en base currency
        
        logger.info(f"Paramètres grille - Spread: {spread:.4f}, Increment: {increment:.6f}")
        return spread, increment
    
    async def setup_grid(self):
        """Configure la grille initiale"""
        try:
            await self.send_telegram_message("🚀 <b>Démarrage du Bot de Trading</b>")
            
            # Calcul des bornes ATR
            lower_bound, upper_bound = await self.calculate_atr_bounds()
            
            # Calcul des paramètres de grille
            spread, increment = self.calculate_grid_parameters(lower_bound, upper_bound)
            
            # Configuration de la grille
            self.grid_config = GridConfig(
                symbol=self.symbol,
                leverage=self.leverage,
                grid_size=self.grid_size,
                budget=self.budget,
                upper_bound=upper_bound,
                lower_bound=lower_bound,
                spread=spread,
                increment=increment,
                stop_loss=self.stop_loss,
                take_profit=self.take_profit
            )
            
            await self.send_telegram_message(
                f"⚙️ <b>Configuration de la Grille</b>\n"
                f"Symbol: {self.symbol}\n"
                f"Budget: {self.budget} USDT\n"
                f"Levier: {self.leverage}x\n"
                f"Taille grille: {self.grid_size}\n"
                f"Bornes: {lower_bound:.2f} - {upper_bound:.2f}\n"
                f"Spread: {spread:.4f}\n"
                f"Increment: {increment:.6f}\n"
                f"Stop Loss: {self.stop_loss*100}%\n"
                f"Take Profit: {self.take_profit*100}%"
            )
            
            # Création des ordres initiaux
            await self.create_initial_orders()
            
        except Exception as e:
            logger.error(f"Erreur setup grille: {e}")
            await self.send_telegram_message(f"❌ Erreur setup grille: {str(e)}")
    
    async def create_initial_orders(self):
        """Crée les ordres initiaux de la grille"""
        try:
            if not self.grid_config:
                logger.error("Configuration de grille non initialisée")
                return
            
            current_price = await self.get_current_price()
            orders_created = 0
            
            # Création des ordres d'achat (en dessous du prix actuel)
            for i in range(self.grid_size // 2):
                price = current_price - (i + 1) * self.grid_config.spread
                if price >= self.grid_config.lower_bound:
                    try:
                        order = await self.place_order('buy', price, self.grid_config.increment)
                        if order:
                            self.active_orders.append(order)
                            orders_created += 1
                    except Exception as e:
                        logger.error(f"Erreur création ordre buy: {e}")
            
            # Création des ordres de vente (au dessus du prix actuel)
            for i in range(self.grid_size // 2):
                price = current_price + (i + 1) * self.grid_config.spread
                if price <= self.grid_config.upper_bound:
                    try:
                        order = await self.place_order('sell', price, self.grid_config.increment)
                        if order:
                            self.active_orders.append(order)
                            orders_created += 1
                    except Exception as e:
                        logger.error(f"Erreur création ordre sell: {e}")
            
            self.persistence.save_orders(self.active_orders)
            
            await self.send_telegram_message(
                f"📋 <b>Ordres Initiaux Créés</b>\n"
                f"Nombre d'ordres: {orders_created}\n"
                f"Prix actuel: {current_price:.2f}"
            )
            
        except Exception as e:
            logger.error(f"Erreur création ordres initiaux: {e}")
            await self.send_telegram_message(f"❌ Erreur création ordres: {str(e)}")
    
    async def place_order(self, side: str, price: float, size: float) -> Optional[Order]:
        """Place un ordre sur KuCoin"""
        try:
            # Simulation pour sandbox ou test
            if self.sandbox:
                order_id = f"test_{datetime.now().timestamp()}"
                order = Order(
                    order_id=order_id,
                    symbol=self.symbol,
                    side=side,
                    size=size,
                    price=price,
                    status='active',
                    created_at=datetime.now()
                )
                logger.info(f"Ordre simulé créé: {side} {size} @ {price}")
                return order
            
            # Placement réel sur KuCoin
            response = self.kucoin_client.add_order(
                symbol=self.symbol,
                side=side,
                type='limit',
                leverage=str(self.leverage),
                size=str(size),
                price=str(price)
            )
            
            if response and 'data' in response:
                order = Order(
                    order_id=response['data']['orderId'],
                    symbol=self.symbol,
                    side=side,
                    size=size,
                    price=price,
                    status='active',
                    created_at=datetime.now()
                )
                logger.info(f"Ordre créé: {order_id} - {side} {size} @ {price}")
                return order
            
        except Exception as e:
            logger.error(f"Erreur placement ordre: {e}")
            return None
    
    async def handle_filled_order(self, filled_order: Order):
        """Gère un ordre rempli et crée l'ordre miroir"""
        try:
            logger.info(f"Ordre rempli: {filled_order.order_id}")
            
            # Calcul du prix pour l'ordre miroir
            if filled_order.side == 'buy':
                # Si achat rempli, créer vente au dessus
                mirror_price = filled_order.price + self.grid_config.spread
                mirror_side = 'sell'
            else:
                # Si vente remplie, créer achat en dessous
                mirror_price = filled_order.price - self.grid_config.spread
                mirror_side = 'buy'
            
            # Vérification des bornes
            if (mirror_side == 'buy' and mirror_price >= self.grid_config.lower_bound) or \
               (mirror_side == 'sell' and mirror_price <= self.grid_config.upper_bound):
                
                # Création de l'ordre miroir
                mirror_order = await self.place_order(mirror_side, mirror_price, filled_order.size)
                if mirror_order:
                    self.active_orders.append(mirror_order)
                    
                    # Calcul du profit
                    profit = filled_order.size * self.grid_config.spread
                    
                    await self.send_telegram_message(
                        f"✅ <b>Ordre Rempli & Miroir Créé</b>\n"
                        f"Rempli: {filled_order.side.upper()} {filled_order.size:.6f} @ {filled_order.price:.2f}\n"
                        f"Miroir: {mirror_side.upper()} {mirror_order.size:.6f} @ {mirror_price:.2f}\n"
                        f"Profit estimé: {profit:.4f} USDT"
                    )
                    
                    # Sauvegarde
                    self.persistence.save_orders(self.active_orders)
                    
                    # Mise à jour PnL
                    await self.update_pnl(profit)
            
            # Suppression de l'ordre rempli de la liste active
            self.active_orders = [o for o in self.active_orders if o.order_id != filled_order.order_id]
            
        except Exception as e:
            logger.error(f"Erreur gestion ordre rempli: {e}")
    
    async def update_pnl(self, profit: float):
        """Met à jour les données PnL"""
        try:
            pnl_data = self.persistence.load_pnl()
            pnl_data['total_pnl'] += profit
            pnl_data['trades'].append({
                'timestamp': datetime.now().isoformat(),
                'profit': profit
            })
            self.persistence.save_pnl(pnl_data)
        except Exception as e:
            logger.error(f"Erreur mise à jour PnL: {e}")
    
    async def check_and_adjust_grid(self):
        """Vérifie et ajuste la grille selon l'ATR"""
        try:
            if not self.grid_config:
                return
            
            now = datetime.now()
            if now - self.last_atr_update < timedelta(minutes=self.adjust_interval):
                return
            
            logger.info("Vérification ajustement grille ATR")
            
            # Recalcul des bornes ATR
            new_lower, new_upper = await self.calculate_atr_bounds()
            
            # Vérification si ajustement nécessaire
            threshold = 0.05  # 5% de différence
            lower_diff = abs(new_lower - self.grid_config.lower_bound) / self.grid_config.lower_bound
            upper_diff = abs(new_upper - self.grid_config.upper_bound) / self.grid_config.upper_bound
            
            if lower_diff > threshold or upper_diff > threshold:
                await self.send_telegram_message("🔄 <b>Ajustement de la grille nécessaire</b>")
                
                # Annulation des ordres existants
                await self.cancel_all_orders()
                
                # Mise à jour de la configuration
                self.grid_config.lower_bound = new_lower
                self.grid_config.upper_bound = new_upper
                
                # Recalcul des paramètres
                spread, increment = self.calculate_grid_parameters(new_lower, new_upper)
                self.grid_config.spread = spread
                self.grid_config.increment = increment
                
                # Recréation des ordres
                await self.create_initial_orders()
                
                await self.send_telegram_message("✅ <b>Grille ajustée avec succès</b>")
            
            self.last_atr_update = now
            
        except Exception as e:
            logger.error(f"Erreur ajustement grille: {e}")
    
    async def cancel_all_orders(self):
        """Annule tous les ordres actifs"""
        try:
            for order in self.active_orders:
                if not self.sandbox:
                    try:
                        self.kucoin_client.cancel_order(order.order_id)
                        logger.info(f"Ordre annulé: {order.order_id}")
                    except Exception as e:
                        logger.error(f"Erreur annulation ordre {order.order_id}: {e}")
            
            self.active_orders.clear()
            self.persistence.save_orders(self.active_orders)
            
        except Exception as e:
            logger.error(f"Erreur annulation ordres: {e}")
    
    async def monitor_orders(self):
        """Surveille les ordres via simulation ou API"""
        while self.running:
            try:
                if self.sandbox:
                    # Simulation de remplissage d'ordres pour test
                    current_price = await self.get_current_price()
                    for order in self.active_orders.copy():
                        # Simulation basique de remplissage
                        if ((order.side == 'buy' and current_price <= order.price) or
                            (order.side == 'sell' and current_price >= order.price)):
                            
                            # Simuler remplissage avec probabilité
                            import random
                            if random.random() < 0.1:  # 10% de chance
                                order.status = 'filled'
                                order.filled_at = datetime.now()
                                await self.handle_filled_order(order)
                
                else:
                    # Vérification réelle des ordres via API
                    for order in self.active_orders.copy():
                        try:
                            response = self.kucoin_client.get_order(order.order_id)
                            if response and response.get('data', {}).get('isActive') == False:
                                order.status = 'filled'
                                order.filled_at = datetime.now()
                                await self.handle_filled_order(order)
                        except Exception as e:
                            logger.error(f"Erreur vérification ordre {order.order_id}: {e}")
                
                # Vérification ajustement grille
                await self.check_and_adjust_grid()
                
                await asyncio.sleep(10)  # Attendre 10 secondes
                
            except Exception as e:
                logger.error(f"Erreur monitoring: {e}")
                await asyncio.sleep(30)
    
    async def start_bot(self):
        """Démarre le bot"""
        try:
            self.running = True
            logger.info("Démarrage du bot de trading")
            
            # Configuration initiale
            await self.setup_grid()
            
            # Démarrage du monitoring
            await self.monitor_orders()
            
        except Exception as e:
            logger.error(f"Erreur démarrage bot: {e}")
            await self.send_telegram_message(f"❌ Erreur démarrage: {str(e)}")
    
    def stop_bot(self):
        """Arrête le bot"""
        self.running = False
        logger.info("Arrêt du bot de trading")

# Commandes Telegram
async def cmd_pnl(update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /pnl"""
    try:
        bot = context.bot_data.get('trading_bot')
        if not bot:
            await update.message.reply_text("❌ Bot non initialisé")
            return
        
        pnl_data = bot.persistence.load_pnl()
        recent_trades = pnl_data['trades'][-10:]  # 10 derniers trades
        
        message = f"📊 <b>PnL Report</b>\n"
        message += f"PnL Total: {pnl_data['total_pnl']:.4f} USDT\n\n"
        message += "<b>Derniers trades:</b>\n"
        
        for trade in recent_trades:
            timestamp = datetime.fromisoformat(trade['timestamp']).strftime('%H:%M:%S')
            message += f"• {timestamp}: +{trade['profit']:.4f} USDT\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Erreur commande PnL: {e}")
        await update.message.reply_text(f"❌ Erreur: {str(e)}")

async def cmd_balance(update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /balance"""
    try:
        bot = context.bot_data.get('trading_bot')
        if not bot:
            await update.message.reply_text("❌ Bot non initialisé")
            return
        
        if bot.sandbox:
            message = f"💰 <b>Balance (Sandbox)</b>\n"
            message += f"Budget initial: {bot.budget} USDT\n"
            message += f"Ordres actifs: {len(bot.active_orders)}\n"
        else:
            # Récupération balance réelle
            try:
                response = bot.kucoin_client.get_account_list()
                message = f"💰 <b>Balance</b>\n"
                if response and 'data' in response:
                    for account in response['data']:
                        if float(account['available']) > 0:
                            message += f"{account['currency']}: {account['available']}\n"
            except:
                message = "❌ Erreur récupération balance"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Erreur commande balance: {e}")
        await update.message.reply_text(f"❌ Erreur: {str(e)}")

def setup_telegram_bot() -> Application:
    """Configure l'application Telegram"""
    application = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()
    
    # Ajout des commandes
    application.add_handler(CommandHandler("pnl", cmd_pnl))
    application.add_handler(CommandHandler("balance", cmd_balance))
    
    return application

async def main():
    """Fonction principale"""
    try:
        # Création du bot de trading
        trading_bot = GridTradingBot()
        
        # Configuration de l'application Telegram
        telegram_app = setup_telegram_bot()
        telegram_app.bot_data['trading_bot'] = trading_bot
        
        # Gestionnaire de signaux pour arrêt propre
        def signal_handler(signum, frame):
            logger.info("Signal d'arrêt reçu")
            trading_bot.stop_bot()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Démarrage des tâches en parallèle
        tasks = [
            trading_bot.start_bot(),
            telegram_app.run_polling()
        ]
        
        await asyncio.gather(*tasks)
        
    except Exception as e:
        logger.error(f"Erreur principale: {e}")

if __name__ == "__main__":
    asyncio.run(main())
