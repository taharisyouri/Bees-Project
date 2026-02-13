from PIL import Image, ImageDraw

# Bee data with names and introductions and colors
BEES_DATA = {
    "Honey Bee": {
        "color": "#FFD700",
        "stripe": "#000000",
        "intro": "The Honey Bee (Apis mellifera) is a highly social insect that lives in colonies of up to 60,000 individuals. They are famous for producing honey and beeswax. Honey bees perform the waggle dance to communicate the location of food sources to other bees. They have complex eyes that can see ultraviolet light and are crucial pollinators for agriculture and wild plants. A single bee colony can visit up to 55,000 flowers in a day. The queen bee can live for 5-7 years while worker bees live only 5-7 weeks."
    },
    "Bumblebee": {
        "color": "#FFB90F",
        "stripe": "#000000",
        "intro": "Bumblebees (Bombus species) are large, fuzzy bees known for their deep buzzing sound. They are excellent pollinators, especially for tomatoes and berries through buzz pollination. Bumblebees can regulate their body temperature, allowing them to forage in cooler weather. Unlike honey bees, they live in smaller colonies of 50-400 bees. They are generally docile and rarely sting unless provoked. Bumblebees are important indicators of ecosystem health and are threatened by habitat loss and pesticides."
    },
    "Carpenter Bee": {
        "color": "#8B4513",
        "stripe": "#FFDAB9",
        "intro": "Carpenter Bees (Xylocopa species) are large, robust bees that nest in wood. Despite their appearance, male carpenter bees cannot sting; only females can. They are solitary bees, meaning each female builds and provisions her own nest. Carpenter bees bore perfectly round holes into wood, creating individual tunnels for their eggs. They are important pollinators for wildflowers and fruits. These bees are often mistaken for bumblebees but are actually larger and less fuzzy."
    },
    "Sweat Bee": {
        "color": "#00FF00",
        "stripe": "#FFFFFF",
        "intro": "Sweat Bees (Halictidae family) are small, often metallic-colored bees attracted to human sweat for its salt content. There are over 4,400 species of sweat bees, making them one of the most diverse bee families. Most species are solitary, though some form small colonies. They are generalist pollinators, visiting various flowers throughout the season. Sweat bees are less aggressive than many other bee species. They play a crucial role in pollinating wild plants and some agricultural crops."
    },
    "Mason Bee": {
        "color": "#4169E1",
        "stripe": "#FFFFFF",
        "intro": "Mason Bees (Osmia species) are solitary bees that nest in cavities and use mud to seal their nesting tubes. They are excellent pollinators, more efficient than honey bees per bee for certain crops like apples and almonds. Mason bees are docile, non-aggressive, and excellent for backyard pollination. Each female bee can lay eggs in multiple cavities. They live a solitary lifestyle, with only the female building and provisioning the nest. Mason bees are increasingly used in commercial orchards for pollination services."
    },
    "Mining Bee": {
        "color": "#FF6347",
        "stripe": "#FFFF00",
        "intro": "Mining Bees (Andrenidae family) excavate tunnels in bare ground or soft banks to create their nests. These solitary bees are among the first to emerge in spring, making them important early-season pollinators. Mining bees are highly specialized, with many species only visiting specific flower species. They are non-aggressive and beneficial for gardens and natural areas. Females work alone to dig, provision, and seal their burrows. Over 1,300 species of mining bees exist worldwide."
    },
    "Orchid Bee": {
        "color": "#00FA9A",
        "stripe": "#00BFFF",
        "intro": "Orchid Bees (Euglofossini tribe) are colorful, iridescent bees found in tropical regions, famous for collecting fragrant compounds from orchids. These solitary and semi-social bees have an extremely long tongue for accessing deep flowers. Male orchid bees create complex pheromone collections used in mate attraction. They are important pollinators for many tropical plants and orchids. Orchid bees are indicators of healthy tropical ecosystems. Some species have metallic green, blue, or gold coloration."
    },
    "Leafcutter Bee": {
        "color": "#DC143C",
        "stripe": "#FFD700",
        "intro": "Leafcutter Bees (Megachile species) cut perfectly circular or oval pieces of leaves to line their nesting tunnels. These solitary bees are excellent pollinators and are less aggressive than many species, though females can sting. They are mid-sized bees with strong jaws adapted for cutting leaves. Leafcutter bees are used commercially for alfalfa and legume pollination. A single acre can support 4,000 nesting females. They are spring and summer bees, with no winter activity in colonies."
    }
}


def create_bee_image(bee_name, width=150, height=150):
    """Create a colorful bee illustration for each bee species"""
    bee_info = BEES_DATA.get(bee_name, {})
    primary_color = bee_info.get("color", "#FFD700")
    stripe_color = bee_info.get("stripe", "#000000")
    
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    body_bbox = [width//4, height//3, 3*width//4, 2*height//3 + 20]
    draw.ellipse(body_bbox, fill=primary_color, outline="#000000", width=2)
    
    stripe_y_positions = [height//2 - 10, height//2 + 10]
    for y in stripe_y_positions:
        draw.line([(width//4 + 10, y), (3*width//4 - 10, y)], fill=stripe_color, width=3)
    
    head_bbox = [width//3 + 10, height//4, 2*width//3 - 10, height//3 + 20]
    draw.ellipse(head_bbox, fill=primary_color, outline="#000000", width=2)
    
    eye_y = height//3 + 5
    draw.ellipse([width//2 - 25, eye_y, width//2 - 15, eye_y + 10], fill="#000000")
    draw.ellipse([width//2 + 15, eye_y, width//2 + 25, eye_y + 10], fill="#000000")
    
    draw.line([(width//2 - 10, height//4), (width//2 - 20, height//5)], fill="#000000", width=2)
    draw.line([(width//2 + 10, height//4), (width//2 + 20, height//5)], fill="#000000", width=2)
    
    wing_positions = [(width//4 - 20, height//2), (3*width//4 + 20, height//2)]
    for wing_x, wing_y in wing_positions:
        draw.ellipse([wing_x - 15, wing_y - 25, wing_x + 15, wing_y + 25], outline="#B0C4DE", width=2)
    
    leg_y = 2*height//3 + 15
    leg_positions = [width//4 + 15, width//2, 3*width//4 - 15]
    for leg_x in leg_positions:
        draw.line([(leg_x, leg_y), (leg_x, leg_y + 20)], fill="#000000", width=2)
    
    return img


def create_dimmed_bee_image(bee_name, width=100, height=100):
    """Create a dimmed/faded bee illustration for background display"""
    pil_image = create_bee_image(bee_name, width, height)
    pil_image = pil_image.convert('RGBA')
    pixels = pil_image.load()
    for i in range(pil_image.width):
        for j in range(pil_image.height):
            r, g, b, a = pixels[i, j]
            gray = int(0.299 * r + 0.587 * g + 0.114 * b)
            pixels[i, j] = (gray, gray, gray, 150)
    bg = Image.new('RGB', pil_image.size, '#f0f8ff')
    bg.paste(pil_image, mask=pil_image.split()[3])
    return bg
