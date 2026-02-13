// export function getCookie(name) {
//  if (document.cookie.length > 0) {
//    c_start = document.cookie.indexOf(name + "=");
//    if (c_start != -1) {
//      c_start = c_start + c_name.length + 1;
//      c_end = document.cookie.indexOf(";", c_start);
//      if (c_end == -1) {
//        c_end = document.cookie.length;
//      }
//      access_token = unescape(document.cookie.substring(c_start, c_end));
//      console.log("loading from document.cookie, access_token = " + access_token);
//      return access_token;
//    }
//    console.log("Could not find cookie with name = " + name)
//    return "";
//  }
//  console.log("Browser is missing cookie.");
//  return "";
// }

export function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift().trim();
}
