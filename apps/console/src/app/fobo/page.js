import { redirect } from 'next/navigation';

// The URL the console used to live at. Old bookmarks land here and are sent
// on to "/", where the console is served now.
export default function Fobo() {
  redirect('/');
}
