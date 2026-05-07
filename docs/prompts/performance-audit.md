Systematic Performance & Rendering Audit
The application is experiencing sluggishness. Perform a read-only analysis to identify bottlenecks, focusing strictly on the Next.js App Router architecture:

1. Network & Data Waterfalls:

Identify N+1 queries or duplicate fetches in React Server Components (RSCs).

Check if we are blocking the UI by awaiting multiple independent database calls sequentially instead of using Promise.all() or React <Suspense> boundaries for streaming.

2. The Client/Server Boundary:

Look for "use client" directives placed too high in the component tree, inadvertently shipping large JavaScript bundles to the browser.

Identify heavy computations happening in client components that should be shifted to the server.

3. Asset & State Optimization:

Verify the use of next/image and next/font. Are we loading unoptimized native <img> tags?

Check for excessive React state changes causing unnecessary re-renders on the main thread.

Provide a prioritized list of optimization strategies. Do not modify the code.