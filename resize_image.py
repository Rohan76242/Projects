from PIL import Image
img = Image.open('test_screen.png').convert('RGB')
img.thumbnail((640, 640))
img.save('test_screen_small.png')
print("Resized. New size:", img.size)