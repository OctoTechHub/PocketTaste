const LINKS = [
  "Audio Description",
  "Help Centre",
  "Gift Cards",
  "Media Centre",
  "Investor Relations",
  "Jobs",
  "Terms of Use",
  "Privacy",
  "Cookie Preferences",
  "Corporate Information",
  "Contact Us",
];

export function SiteFooter() {
  return (
    <footer className="mt-8 px-4 py-10 text-sm text-white/50 sm:px-12">
      <p className="mb-6">Questions? Call 000-800-000-0000</p>
      <ul className="grid max-w-3xl grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 md:grid-cols-4">
        {LINKS.map((link) => (
          <li key={link}>
            <a href="#" className="transition-colors hover:text-white/80 hover:underline">
              {link}
            </a>
          </li>
        ))}
      </ul>
      <p className="mt-6 text-xs text-muted-foreground">
        StreamHub — a demo streaming UI. Audio stories are public-domain LibriVox recordings.
      </p>
    </footer>
  );
}
