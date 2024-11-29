function irrelevant(arguments) {
  let element = arguments[0];
  let computedStyle = window.getComputedStyle(element);
  let bgColor = computedStyle.backgroundColor;

  let mergedColor = parseRGBA(bgColor);
  while (element && mergedColor[3] < 1) {
    element = element.parentElement;
    if (element === null) {
      break
    }
    const parentBgColor = parseRGBA(window.getComputedStyle(element).backgroundColor);
    mergedColor = blendColors(mergedColor, parentBgColor);
  }
  return mergedColor.slice(0, 3)

  function parseRGBA(color) {
    if (color.startsWith('rgba')) {
      const rgba = color.match(/rgba?\((\d+), (\d+), (\d+),? ([\d\.]+)?\)/);
      return [parseInt(rgba[1], 10), parseInt(rgba[2], 10), parseInt(rgba[3], 10), parseFloat(rgba[4])]
    } else {
      const rgb = color.match(/rgb?\((\d+), (\d+), (\d+)\)/);
      return [parseInt(rgb[1], 10), parseInt(rgb[2], 10), parseInt(rgb[3], 10), 1.0]
    }
  }

  function blendColors(fgColor, bgColor) {
    const alpha = fgColor[3] + bgColor[3] * (1 - fgColor[3]);
    const red = Math.round((fgColor[0] * fgColor[3] + bgColor[0] * bgColor[3] * (1 - fgColor[3])) / alpha);
    const green = Math.round((fgColor[1] * fgColor[3] + bgColor[1] * bgColor[3] * (1 - fgColor[3])) / alpha);
    const blue = Math.round((fgColor[2] * fgColor[3] + bgColor[2] * bgColor[3] * (1 - fgColor[3])) / alpha);
    return [red, green, blue, alpha];
  }

}
