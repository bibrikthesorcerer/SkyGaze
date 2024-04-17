from django.http import HttpResponseNotFound, JsonResponse #HttpResponse
from django.shortcuts import redirect, render
from mainApp.api import get_visible_constells, get_constells, get_time_date, get_constell_by_id, scrape_wiki_page, get_wiki_cached

def index(request):
	"""
	Render the index page with the current date and time.

	Args:
		request: The HTTP request object.

	Returns:
		HttpResponse: The rendered index page.
	"""
	d,t = get_time_date()
	return render(request, 'mainApp/home.html', {"DATE":d, "TIME":t})

def session(request):
	"""
	Handle the session request to calculate and display the visible constellations based on user input.

	Args:
		request: The HTTP request object containing user input data in POST dictionary.

	Returns:
		HttpResponse: The rendered session page displaying the visible constellations and relevant information.
	"""
	post = request.POST
	visible, post = get_visible_constells(post['long'], post['lat'], post['time'], post['date'])
	return render(request, 'mainApp/session.html', {'visible': visible, 'how_many': len(visible), 'POST' : post})

def constells(request):
	"""
	Render the constellations page with the list of constellations and current date and time.

	Args:
		request: The HTTP request object.

	Returns:
		HttpResponse: The rendered constellations page with the list of constellations and current date and time.
	"""
	constells = get_constells()
	d,t = get_time_date()
	return render(request, 'mainApp/constellations.html', {"constells": constells, "DATE":d, "TIME":t})

def get_by_id(request):
	"""
	Find constellation in MongoDB using ObjectId's id-string (ex 65469404c1e20947088ca732)

	Args:
		request: http request containing id-string as "id" in GET-method dictionary.
	
	Returns:
		Json-object with fields {_id, name, ra, dec, wiki}
	"""
	constell_id = request.GET.get('constell_id')
	constell = get_constell_by_id(int(constell_id))
	return JsonResponse(constell)

def get_wiki_page(request):
	"""
	Retrieve and return data from a Wikipedia page related to a specific constellation.

	Args:
		request: The HTTP request object containing the constellation ID.

	Returns:
		JsonResponse: JSON response containing data extracted from the Wikipedia page.
	"""
	constell_id = request.GET.get('constell_id')
	constell = get_constell_by_id(int(constell_id))
	wiki_url_suffix = constell['wiki'].split('/')[-1]
	wiki_url = f'https://en.wikipedia.org/w/api.php?action=parse&page={wiki_url_suffix}&format=json'
	const_data = get_wiki_cached(wiki_url, wiki_url_suffix)
	const_data.update({"name": constell['name'], "wiki":constell['wiki']})
	return JsonResponse(const_data)

def pageNotFound(request, exception):
	"""
	Handle the page not found error by returning an HTTP 404 response.

	Args:
		request: The HTTP request object.
		exception: The exception that triggered the page not found error.

	Returns:
		HttpResponseNotFound: An HTTP response indicating that the page was not found.
	"""
	return HttpResponseNotFound("<h1>Page Not Found</h1>")

def wiki_redirect(request, suffix):
	"""
	Redirect to the Wikipedia page with the provided suffix.

	Args:
		request: The HTTP request object.
		suffix (str): The suffix to append to the Wikipedia URL.

	Returns:
		Redirect: Redirects the user to the corresponding Wikipedia page.
	"""
	return redirect(f"https://en.wikipedia.org/wiki/{suffix}")