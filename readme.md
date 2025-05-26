# 📈 Bot de Trading Telegram - Stratégie de Grille Adaptative KuCoin

Un bot de trading automatisé utilisant une stratégie de grille adaptative sur KuCoin Futures, avec notifications Telegram en temps réel.

## 🚀 Fonctionnalités

### Stratégie de Trading
- **Grille Adaptative** : Ordres d'achat/vente à intervalles fixes optimisés
- **ATR (Average True Range)** : Calcul automatique des bornes de grille selon la volatilité
- **Ajustement Dynamique** : Recalibrage périodique de la grille (15min par défaut)
- **Ordres Miroir** : Création automatique d'ordres opposés lors du remplissage
- **Stop Loss / Take Profit** : Protection configurable des positions

### Intégration KuCoin
- Support **KuCoin Futures** avec levier configurable (10x par défaut)
- Paire **BTC/USDT:USDT** par défaut (configurable)
- Gestion automatique des ordres via WebSocket et API REST
- Mode **Sandbox** pour tests sans risque

### Notifications Telegram
- **Logs en temps réel** : Toutes les actions et décisions du bot
- **Commandes interactives** :
  - `/pnl` - Affichage du PnL et historique des trades
  - `/balance` - Consultation du solde du compte
- **Alertes automatiques** : Ordres remplis, ajustements de grille, erreurs

### Persistance des Données
- Sauvegarde automatique des ordres et historique PnL
- Logs détaillés dans le répertoire `DATA_DIR`
- Récupération automatique après redémarrage

## 📋 Prérequis

### Comptes Requis
1. **Compte KuCoin** avec API activée
2. **Bot Telegram** créé via @BotFather
3. **Chat/Channel Telegram** pour recevoir les notifications

### Clés API KuCoin
1. Connectez-vous à KuCoin
2. Allez dans **API Management**
3. Créez une nouvelle API avec permissions :
   - ✅ General
   - ✅ Futures Trading
4. Notez : `API Key`, `Secret`, `Passphrase`

### Bot Telegram
1. Contactez @BotFather sur Telegram
2. Créez un nouveau bot : `/newbot`
3. Récupérez le **Token** du bot
4. Obtenez votre **Chat ID** (utilisez @userinfobot)

## ⚙️ Configuration

### Variables d'Environnement

Créez un fichier `.env` basé sur `.env.example` :

```bash
# KuCoin SDK Settings
KUCOIN_API_KEY=votre_api_key
KUCOIN_API_SECRET=votre_api_secret
KUCOIN_API_PASSPHRASE=votre_passphrase

# Telegram
TELEGRAM_TOKEN=votre_bot_token
TELEGRAM_CHAT_ID=votre_chat_id

# Stratégie
SYMBOL=BTC-USDT
LEVERAGE=10
GRID_SIZE=10
ADJUST_INTERVAL_MIN=15
STOP_LOSS=0.01
TAKE_PROFIT=0.02
BUDGET=1000

# Environnement
SANDBOX=true
LOG_LEVEL=INFO
DATA_DIR=./data
```

### Paramètres de Stratégie

| Paramètre | Description | Valeur par défaut |
|-----------|-------------|-------------------|
| `SYMBOL` | Paire de trading | BTC-USDT |
| `LEVERAGE` | Effet de levier | 10 |
| `GRID_SIZE` | Nombre d'ordres dans la grille | 10 |
| `ADJUST_INTERVAL_MIN` | Intervalle d'ajustement ATR (minutes) | 15 |
| `STOP_LOSS` | Stop Loss en pourcentage | 0.01 (1%) |
| `TAKE_PROFIT` | Take Profit en pourcentage | 0.02 (2%) |
| `BUDGET` | Budget de départ en USDT | 1000 |

## 🚀 Déploiement

### Option 1 : Déploiement Local

1. **Cloner et installer** :
```bash
git clone <repository>
cd kucoin-trading-bot
pip install -r requirements.txt
```

2. **Configuration** :
```bash
cp .env.example .env
# Éditer .env avec vos paramètres
```

3. **Lancer** :
```bash
python main.py
```

### Option 2 : Déploiement sur Render.com

1. **Fork ce repository** sur GitHub

2. **Créer un nouveau service** sur Render :
   - Type : **Web Service**
   - Repository : Votre fork
   - Runtime : **Python 3**
   - Build Command : `pip install -r requirements.txt`
   - Start Command : `python main.py`

3. **Configurer les variables d'environnement** dans Render :
   - Ajouter toutes les variables du fichier `.env`
   - ⚠️ **Important** : Garder `SANDBOX=true` pour les tests

4. **Déployer** et surveiller les logs

### Option 3 : Docker

```bash
# Build
docker build -t kucoin-trading-bot .

# Run
docker run -d --env-file .env kucoin-trading-bot
```

## 📊 Utilisation

### Démarrage du Bot

1. **Mode Sandbox** (recommandé pour débuter) :
   - Définir `SANDBOX=true`
   - Le bot simulera les trades sans argent réel

2. **Mode Production** :
   - Définir `SANDBOX=false`
   - ⚠️ **Attention** : Trades réels avec argent véritable

### Commandes Telegram

- `/pnl` : Affiche le PnL total et l'historique des 10 derniers trades
- `/balance` : Consulte le solde du compte (sandbox ou réel)

### Surveillance

Le bot envoie automatiquement des notifications pour :
- 🚀 Démarrage et configuration
- ⚙️ Paramètres de grille calculés
- 📋 Création des ordres initiaux
- ✅ Ordres remplis et création d'ordres miroir
- 🔄 Ajustements de grille basés sur l'ATR
- ❌ Erreurs et alertes

## 🔧 Architecture

### Structure du Projet
```
kucoin-trading-bot/
├── main.py              # Bot principal
├── requirements.txt     # Dépendances Python
├── Dockerfile          # Configuration Docker
├── render.yaml         # Configuration Render
├── .env.example        # Exemple de configuration
├── README.md           # Documentation
└── data/               # Répertoire de persistance
    ├── orders.json     # Ordres sauvegardés
    ├── pnl.json        # Historique PnL
    └── bot.log         # Logs détaillés
```

### Classes Principales

- **`GridTradingBot`** : Logique principale du bot
- **`ATRCalculator`** : Calcul de l'Average True Range
- **`DataPersistence`** : Gestion de la sauvegarde
- **`Order`** : Représentation des ordres
- **`GridConfig`** : Configuration de la grille

### Flux d'Exécution

1. **Initialisation** : Chargement config, connexion APIs
2. **Calcul ATR** : Analyse de la volatilité du marché
3. **Setup Grille** : Définition des bornes et paramètres
4. **Création Ordres** : Placement des ordres initiaux
5. **Monitoring** : Surveillance continue des remplissages
6. **Ajustement** : Recalibrage périodique selon l'ATR

## ⚠️ Sécurité et Risques

### Recommandations de Sécurité
- 🔐 **Ne jamais partager** vos clés API
- 🧪 **Tester en Sandbox** avant le mode production
- 💰 **Commencer avec un petit budget**
- 📊 **Surveiller régulièrement** les performances

### Risques de Trading
- 📉 **Pertes possibles** : Le trading comporte des risques
- 🎯 **Volatilité** : Les marchés crypto sont très volatils
- ⚡ **Effet de levier** : Amplifie gains ET pertes
- 🔄 **Grille** : Peut accumuler des positions perdantes

### Gestion des Risques
- 🛑 **Stop Loss** : Limite les pertes maximales
- 💎 **Take Profit** : Sécurise les gains
- 📊 **ATR** : Adaptation à la volatilité
- 🔍 **Monitoring** : Surveillance en temps réel

## 🛠️ Dépannage

### Problèmes Courants

**Bot ne démarre pas** :
- Vérifier les variables d'environnement
- Contrôler les clés API KuCoin
- Tester la connexion Telegram

**Ordres non créés** :
- Vérifier les permissions API
- Contrôler le solde du compte
- Vérifier les paramètres de levier

**Notifications Telegram manquantes** :
- Vérifier le token du bot
- Contrôler le Chat ID
- Tester avec @userinfobot

### Logs

Consultez les logs détaillés :
```bash
# Local
tail -f bot.log

# Render
Consulter les logs dans le dashboard
```

## 📈 Optimisation

### Paramètres Recommandés

**Pour débuter** :
- `BUDGET=100`
- `GRID_SIZE=6`
- `LEVERAGE=3`
- `SANDBOX=true`

**Trading actif** :
- `ADJUST_INTERVAL_MIN=5`
- `GRID_SIZE=15`
- Surveillance ATR fréquente

**Marchés volatils** :
- `STOP_LOSS=0.005` (0.5%)
- `TAKE_PROFIT=0.015` (1.5%)
- Grille plus large

## 🤝 Support

Pour questions et support :
1. 📖 Consulter cette documentation
2. 🔍 Vérifier les logs d'erreur
3. 🧪 Tester en mode sandbox
4. 📧 Ouvrir une issue GitHub

## ⚖️ Licence

Ce projet est fourni à des fins éducatives. Utilisez-le à vos risques et périls.

**Disclaimer** : Le trading de cryptomonnaies comporte des risques financiers importants. Ne tradez que ce que vous pouvez vous permettre de perdre.