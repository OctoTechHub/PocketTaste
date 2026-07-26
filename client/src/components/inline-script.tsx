/**
 * Renders an inline <script> that the browser executes synchronously while it
 * parses the HTML — i.e. before the first paint, and before React is involved.
 *
 * React warns in development whenever a component renders a <script> tag, since
 * scripts inserted by a DOM update never execute. Emitting `text/javascript` on
 * the server and `text/plain` on the client keeps the warning away and makes the
 * intent explicit: this only ever runs on a hard navigation. On soft navigations
 * the tag is inert, so whatever the script does must also be handled in React.
 */
export function InlineScript({ html }: { html: string }) {
  return (
    <script
      type={typeof window === "undefined" ? "text/javascript" : "text/plain"}
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
