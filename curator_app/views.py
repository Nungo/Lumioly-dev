from django.shortcuts import render, get_object_or_404
from .models import NewsItem, AiTool, Category
import requests
import os
from datetime import datetime
from django.http import HttpResponse, HttpResponseForbidden
from django.core.management import call_command

# Gemini client function
from .ai_client import get_explanation


def home_view(request):
    """
    View for the homepage with AI search functionality and live news.
    """
    # Get live news for home page
    try:
        api_key = os.environ.get('NEWSDATA_API_KEY')
        if api_key:
            latest_news = fetch_real_time_news('AI technology', '', api_key)[:3]
        else:
            latest_news = []
        
        # Fallback to database or sample
        if len(latest_news) < 2:
            db_news = list(NewsItem.objects.all().order_by('-published_date')[:3])
            if db_news:
                latest_news = db_news
            else:
                latest_news = create_sample_news()[:3]
    except:
        latest_news = create_sample_news()[:3]
    
    latest_tools = AiTool.objects.all().order_by('-added_date')[:5]
    
    # Get conversation history from session
    conversation_history = request.session.get('ai_conversation', [])
    
    # Handle AI search from the home page
    if request.method == 'POST':
        # Check if clearing history
        if request.POST.get('clear_history'):
            request.session['ai_conversation'] = []
            conversation_history = []
        else:
            ai_query = request.POST.get('ai_query')
            if ai_query:
                # Get AI explanation using Gemini
                ai_response = get_explanation(ai_query)
                
                # Add to conversation history
                conversation_entry = {
                    'query': ai_query,
                    'response': ai_response,
                    'timestamp': datetime.now().strftime('%H:%M')
                }
                conversation_history.append(conversation_entry)
                
                # Keep only last 5 conversations to avoid session bloat
                if len(conversation_history) > 5:
                    conversation_history = conversation_history[-5:]
                
                # Save back to session
                request.session['ai_conversation'] = conversation_history
    
    context = {
        'latest_news': latest_news,
        'latest_tools': latest_tools,
        'conversation_history': conversation_history,
        'news_count': len(latest_news),
    }
    return render(request, 'home.html', context)


def news_list_view(request):
    """
    View to display news with real-time search using NewsData.io API.
    """
    news_items = []
    error_message = None
    news_source = "live"
    
    # Get search parameters
    search_query = request.GET.get('search', '')
    category = request.GET.get('category', '')
    
    # Always try API first
    api_key = os.environ.get('NEWSDATA_API_KEY')
    if api_key:
        try:
            print(f"Attempting to fetch news with API key: {api_key[:10]}...")  # Debug
            news_items = fetch_real_time_news(search_query, category, api_key)
            
            if news_items:
                print(f"SUCCESS: Got {len(news_items)} articles from API")  # Debug
            else:
                print("API returned no articles, trying fallback...")  # Debug
                
        except Exception as e:
            print(f"API Exception: {e}")  # Debug
            error_message = f"API error: {str(e)}"
    else:
        print("No API key found in environment")  # Debug
        error_message = "No API key configured"
    
    # Fallback to sample news if API fails
    if not news_items:
        print("Using sample news as fallback")  # Debug
        news_items = create_sample_news()
        news_source = "sample"
        if not error_message:
            error_message = "Using sample news (API may be limited)"
    
    context = {
        'news_items': news_items,
        'page_title': 'All AI News',
        'search_query': search_query,
        'category': category,
        'error_message': error_message,
        'news_source': news_source,
        'news_count': len(news_items),
    }
    return render(request, 'curator_app/news_list.html', context)


def create_sample_news():
    """Create sample AI news for demo purposes"""
    from datetime import datetime, timedelta
    
    sample_articles = [
        {
            'title': 'OpenAI Releases GPT-4 Turbo with Enhanced Reasoning Capabilities',
            'summary': 'OpenAI announced a major update to GPT-4 Turbo, featuring improved reasoning abilities and faster response times. The new model shows significant improvements in mathematical problem-solving and code generation tasks.',
            'source': 'TechCrunch',
            'link': 'https://techcrunch.com/2024/11/06/openai-announces-gpt-4-turbo/',
            'date': datetime.now() - timedelta(hours=2)
        },
        {
            'title': 'Google DeepMind Unveils Breakthrough in AI Protein Folding',
            'summary': 'Researchers at Google DeepMind have announced a new AI system that can predict protein structures with unprecedented accuracy, potentially revolutionizing drug discovery and medical research.',
            'source': 'Nature',
            'link': 'https://www.nature.com/articles/s41586-021-03819-2',
            'date': datetime.now() - timedelta(hours=5)
        },
        {
            'title': 'Microsoft Copilot Integration Expands to Enterprise Applications',
            'summary': 'Microsoft announced expanded Copilot integration across its enterprise suite, bringing AI assistance to Excel, PowerPoint, and Teams with new productivity features for business users.',
            'source': 'Microsoft Blog',
            'link': 'https://blogs.microsoft.com/blog/2023/03/16/introducing-microsoft-365-copilot/',
            'date': datetime.now() - timedelta(hours=8)
        },
        {
            'title': 'Anthropic Claude 3 Shows Superior Performance in Code Generation',
            'summary': 'Latest benchmarks reveal that Anthropic\'s Claude 3 model demonstrates exceptional performance in software development tasks, competing closely with GPT-4 in programming challenges.',
            'source': 'AI Research Weekly',
            'link': 'https://www.anthropic.com/news/claude-3-family',
            'date': datetime.now() - timedelta(days=1)
        },
        {
            'title': 'AI Startup Perplexity Raises $73M for Search Innovation',
            'summary': 'Perplexity AI announced a $73 million funding round to expand its AI-powered search platform, positioning itself as a competitor to traditional search engines with conversational AI.',
            'source': 'VentureBeat',
            'link': 'https://venturebeat.com/ai/perplexity-ai-raises-73-5m-series-b/',
            'date': datetime.now() - timedelta(days=2)
        }
    ]
    
    news_items = []
    for i, article in enumerate(sample_articles):
        news_item = type('NewsItem', (), {
            'title': article['title'],
            'summary': article['summary'],
            'link': article['link'],  # Real working links now!
            'published_date': article['date'],
            'source': type('Source', (), {'name': article['source']})(),
            'id': i + 1000,
        })()
        news_items.append(news_item)
    
    return news_items


def fetch_real_time_news(search_query='', category='', api_key=''):
    """
    Fetch real-time AI-focused news from NewsData.io API
    """
    url = "https://newsdata.io/api/1/news"
    
    # Make searches more AI-specific and current
    if not search_query:
        ai_keywords = [
            'artificial intelligence breakthrough',
            'machine learning latest',
            'AI model release',
            'ChatGPT OpenAI',
            'Google AI Gemini',
            'AI startup funding',
        ]
        search_query = ai_keywords[0]  # Default to breakthrough news
    
    params = {
        'apikey': api_key,
        'q': f"{search_query} AI artificial intelligence",  # Always include AI context
        'language': 'en',
        'size': 15,  # Get more for better filtering
        'timeframe': '7d',  # Last 7 days for current trends
    }
    
    # Add category if specified
    if category:
        category_mapping = {
            'research': 'science',
            'industry': 'business', 
            'tools': 'technology',
            'policy': 'politics'
        }
        params['category'] = category_mapping.get(category, 'technology')
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Filter out non-AI related articles and convert to our format
        news_items = []
        ai_keywords = ['AI', 'artificial intelligence', 'machine learning', 'deep learning', 
                      'neural network', 'ChatGPT', 'OpenAI', 'Google', 'tech', 'algorithm',
                      'automation', 'robot', 'data science', 'ML', 'AGI']
        
        for article in data.get('results', []):
            title = article.get('title', '').lower()
            description = article.get('description', '').lower()
            
            # Check if article is AI-related
            is_ai_related = any(keyword.lower() in title or keyword.lower() in description 
                              for keyword in ai_keywords)
            
            if is_ai_related:
                news_item = type('NewsItem', (), {
                    'title': article.get('title', 'No title'),
                    'summary': article.get('description', 'No description available')[:200] + '...',
                    'link': article.get('link', '#'),
                    'published_date': parse_date(article.get('pubDate')),
                    'source': type('Source', (), {
                        'name': article.get('source_id', 'Unknown Source').title()
                    })(),
                    'id': hash(article.get('title', '')) % 10000,
                })()
                news_items.append(news_item)
                
                # Limit to 10 high-quality AI articles
                if len(news_items) >= 10:
                    break
            
        return news_items
        
    except requests.RequestException as e:
        print(f"NewsData.io API error: {e}")
        return []
    except Exception as e:
        print(f"Error processing news data: {e}")
        return []


def parse_date(date_string):
    """
    Parse date string from NewsData.io API
    """
    if not date_string:
        return datetime.now()
    
    try:
        # NewsData.io uses ISO format: 2024-05-28T10:30:00Z
        return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
    except:
        return datetime.now()


def tool_list_view(request):
    """
    View to display a full list of all AI tools with filtering.
    """
    ai_tools = AiTool.objects.all()
    
    # Handle search and filtering
    search_query = request.GET.get('search', '')
    category = request.GET.get('category', '')
    sort_order = request.GET.get('sort', 'name')
    
    if search_query:
        ai_tools = ai_tools.filter(name__icontains=search_query)
    
    if category:
        ai_tools = ai_tools.filter(category=category)
    
    # Sorting
    if sort_order == '-name':
        ai_tools = ai_tools.order_by('-name')
    elif sort_order == 'popular':
        ai_tools = ai_tools.order_by('-id')  # Assuming newer = more popular
    elif sort_order == 'recent':
        ai_tools = ai_tools.order_by('-added_date')
    else:
        ai_tools = ai_tools.order_by('name')
    
    context = {
        'ai_tools': ai_tools,
        'page_title': 'All AI Tools & Products',
        'search_query': search_query,
        'category': category,
        'sort_order': sort_order,
    }
    return render(request, 'curator_app/tool_list.html', context)


def tool_detail_view(request, pk):
    """
    View to display details for a single AI tool and handle AI explanation requests.
    """
    tool = get_object_or_404(AiTool, pk=pk)
    explanation = None

    # Form submission when user clicks "Ask AI" button
    if request.method == 'POST':
        query = tool.perplexity_query
        if query:
            # Call ai_client function to get AI response
            explanation = get_explanation(query)
        else:
            explanation = "No specific query is configured for this tool in the admin panel."

    context = {
        'tool': tool,
        'explanation': explanation,
    }
    return render(request, 'curator_app/tool_detail.html', context)


def trigger_fetch_news_view(request, secret):
    """
    A secure view to trigger the fetch_news management command.
    """
    # Ensure valid credentials
    if secret != os.environ.get('CRON_SECRET'):
        # If they don't match - 'Forbidden' error
        return HttpResponseForbidden('Invalid secret.')

    try:
        print("Cron job triggered: Fetching news...")
        call_command('fetch_news')
        print("Cron job finished successfully.")
        return HttpResponse('News fetch command triggered successfully.')
    except Exception as e:
        # Log errors and throw error response
        print(f"Error running fetch_news command via cron: {e}")
        return HttpResponse(f'Error triggering command: {e}', status=500)