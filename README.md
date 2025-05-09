# BraveDrop

**BraveDrop** is a demonstration site for CS:GO-style case openings built with Django. It showcases core mechanics from user authentication to external API integration.

## ⚙️ Features

- **Steam OpenID Login**
- **Test Item Retrieval** using the `market.csgo.com` API
- **Case Opening**: random item drops with visual effects
- **Upgrade Mode**: combine multiple items into one with success probability
- **Contract Mode**: swap several skins for a new one with randomized outcome
- **Automated Price Updates** via external API
- **Case Import** from `wiki.cs.money`
- **Admin Panel** restricted by whitelist IPs
- **Additional Utilities**: trade link parser, Steam profile giveaway parser

## 🚀 Installation & Running

1. **Clone the repository**:
   ```bash
   git clone https://github.com/2F28/BraveDropProject.git
   cd BraveDropProject
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Copy the example environment file**:
   ```bash
   cp .env.example .env
   ```
4. **Fill in the `.env` file** with your values:
   ```env
   DJANGO_SECRET_KEY=dummy-dev-key
   DJANGO_DEBUG=false
   DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
   ADMIN_ALLOWED_IPS=127.0.0.1
   STEAM_API_KEY=your_steam_api_key
   MARKETCSGO_API_KEY=your_market_api_key
   ```
   - **DJANGO_SECRET_KEY**: any string for development
   - **ADMIN_ALLOWED_IPS**: IP addresses allowed to access the admin panel
   - **STEAM_API_KEY**: obtain one from [Steam API](https://steamcommunity.com/dev/apikey)
   - **MARKETCSGO_API_KEY**: obtain one from [market.csgo.com API](https://market.csgo.com/en/api)
5. **Apply migrations and start the server**:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

> **Note:** To enable automated price updates, run `scheduler.py` (e.g., via a cron job).

## 📂 Repository Structure

```text
BraveDropProject/
├── Center/              
├── main/      
├── media/              
├── static/   
├── staticfiles/             
├── templates/          
├── manage.py             
├── requirements.txt    
├── .env.example        
├── .gitignore            
└── README.md            
```

## ⚠️ Additional Information

- Real monetary transactions are **not implemented**.
- Valid API keys and sufficient market balance are required for item retrieval.
- Project is released under the MIT License.

## 📄 License

This project is licensed under the **MIT License**. See [LICENSE](./LICENSE) for details.
