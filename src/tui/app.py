"""Main TUI application using Textual."""
import threading
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Header, Footer, Button, Static, Input, Label, TextArea, OptionList, LoadingIndicator, ProgressBar
from textual.widgets.option_list import Option
from textual.binding import Binding
from textual.screen import Screen
from textual.worker import Worker, WorkerState
from loguru import logger

from src.orchestrator import orchestrator
from src.database import db


class WelcomeScreen(Screen):
    """Welcome screen with main menu."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static(
                """
[bold cyan]Multi-Agent AI Workflow[/]


[yellow]Choose an option:[/]
""",
                id="welcome_text",
            ),
            Button("🚀 New Customer Setup", id="btn_new_customer", variant="primary"),
            Button("🔍 Research Topics", id="btn_research", variant="success"),
            Button("✍️  Create Post", id="btn_create_post", variant="success"),
            Button("📊 View Status", id="btn_status", variant="default"),
            Button("❌ Exit", id="btn_exit", variant="error"),
            id="menu_container",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "btn_new_customer":
            self.app.push_screen(NewCustomerScreen())
        elif button_id == "btn_research":
            self.app.push_screen(ResearchScreen())
        elif button_id == "btn_create_post":
            self.app.push_screen(CreatePostScreen())
        elif button_id == "btn_status":
            self.app.push_screen(StatusScreen())
        elif button_id == "btn_exit":
            self.app.exit()


class NewCustomerScreen(Screen):
    """Screen for setting up a new customer."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield ScrollableContainer(
            Static("[bold cyan]═══ New Customer Setup ═══[/]\n", id="title"),

            # Basic Info Section
            Static("[bold yellow]Basic Information[/]"),
            Label("Customer Name *:"),
            Input(placeholder="Enter customer name", id="input_name"),

            Label("LinkedIn URL *:"),
            Input(placeholder="https://www.linkedin.com/in/username", id="input_linkedin"),

            Label("Company Name:"),
            Input(placeholder="Enter company name", id="input_company"),

            Label("Email:"),
            Input(placeholder="customer@example.com", id="input_email"),

            # Persona Section
            Static("\n[bold yellow]Persona[/]"),
            Label("Describe the customer's persona, expertise, and positioning:"),
            TextArea(id="input_persona"),

            # Form of Address
            Static("\n[bold yellow]Communication Style[/]"),
            Label("Form of Address:"),
            Input(placeholder="e.g., Duzen (Du/Euch) or Siezen (Sie)", id="input_address"),

            # Style Guide
            Label("Style Guide:"),
            Label("Describe writing style, tone, and guidelines:"),
            TextArea(id="input_style_guide"),

            # Topic History
            Static("\n[bold yellow]Content History[/]"),
            Label("Topic History (comma separated):"),
            Label("Enter previous topics covered:"),
            TextArea(id="input_topic_history"),

            # Example Posts
            Label("Example Posts (separate with --- on new line):"),
            Label("Paste example posts to analyze writing style:"),
            TextArea(id="input_example_posts"),

            # Actions
            Static("\n"),
            Horizontal(
                Button("Cancel", id="btn_cancel", variant="error"),
                Button("Start Setup", id="btn_start", variant="primary"),
                id="button_row"
            ),

            # Status/Progress area
            Container(
                Static("", id="status_message"),
                id="status_container"
            ),

            id="form_container",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn_cancel":
            self.app.pop_screen()
        elif event.button.id == "btn_start":
            self.start_setup()

    def start_setup(self) -> None:
        """Start the customer setup process."""
        # Get inputs
        name = self.query_one("#input_name", Input).value.strip()
        linkedin_url = self.query_one("#input_linkedin", Input).value.strip()
        company = self.query_one("#input_company", Input).value.strip()
        email = self.query_one("#input_email", Input).value.strip()
        persona = self.query_one("#input_persona", TextArea).text.strip()
        form_of_address = self.query_one("#input_address", Input).value.strip()
        style_guide = self.query_one("#input_style_guide", TextArea).text.strip()
        topic_history_raw = self.query_one("#input_topic_history", TextArea).text.strip()
        example_posts_raw = self.query_one("#input_example_posts", TextArea).text.strip()

        status_widget = self.query_one("#status_message", Static)

        if not name or not linkedin_url:
            status_widget.update("[red]✗ Please fill in required fields (Name and LinkedIn URL)[/]")
            return

        # Parse topic history
        topic_history = [t.strip() for t in topic_history_raw.split(",") if t.strip()]

        # Parse example posts
        example_posts = [p.strip() for p in example_posts_raw.split("---") if p.strip()]

        # Disable buttons during setup
        self.query_one("#btn_start", Button).disabled = True
        self.query_one("#btn_cancel", Button).disabled = True

        # Show progress steps
        status_widget.update("[bold cyan]Starting setup process...[/]\n")

        customer_data = {
            "company_name": company,
            "email": email,
            "persona": persona,
            "form_of_address": form_of_address,
            "style_guide": style_guide,
            "topic_history": topic_history,
            "example_posts": example_posts
        }

        # Show what's happening
        status_widget.update(
            "[bold cyan]⏳ Step 1/5: Creating customer record...[/]\n"
            "[bold cyan]⏳ Step 2/5: Creating LinkedIn profile...[/]\n"
            "[bold cyan]⏳ Step 3/5: Scraping LinkedIn posts...[/]\n"
            "[yellow]   This may take 1-2 minutes...[/]"
        )

        # Run setup in background worker
        self.run_worker(
            self._run_setup_worker(linkedin_url, name, customer_data),
            name="setup_worker",
            group="setup",
            exclusive=True
        )

    async def _run_setup_worker(self, linkedin_url: str, name: str, customer_data: dict):
        """Worker method to run setup in background."""
        return await orchestrator.run_initial_setup(
            linkedin_url=linkedin_url,
            customer_name=name,
            customer_data=customer_data
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.worker.name != "setup_worker":
            return

        status_widget = self.query_one("#status_message", Static)

        if event.state == WorkerState.SUCCESS:
            # Worker completed successfully
            customer = event.worker.result
            status_widget.update(
                "[bold green]✓ Step 1/5: Customer record created[/]\n"
                "[bold green]✓ Step 2/5: LinkedIn profile created[/]\n"
                "[bold green]✓ Step 3/5: LinkedIn posts scraped[/]\n"
                "[bold green]✓ Step 4/5: Profile analyzed[/]\n"
                "[bold green]✓ Step 5/5: Topics extracted[/]\n\n"
                f"[bold cyan]═══ Setup Complete! ═══[/]\n"
                f"[green]Customer ID: {customer.id}[/]\n"
                f"[green]Name: {customer.name}[/]\n\n"
                "[yellow]You can now research topics or create posts.[/]"
            )
            logger.info(f"Setup completed for customer: {customer.id}")
        elif event.state == WorkerState.ERROR:
            # Worker failed
            error = event.worker.error
            logger.exception(f"Setup failed: {error}")
            status_widget.update(
                f"[bold red]✗ Setup Failed[/]\n\n"
                f"[red]Error: {str(error)}[/]\n\n"
                f"[yellow]Please check the error and try again.[/]"
            )
            self.query_one("#btn_start", Button).disabled = False
            self.query_one("#btn_cancel", Button).disabled = False
        elif event.state == WorkerState.CANCELLED:
            # Worker was cancelled
            status_widget.update("[yellow]Setup cancelled[/]")
            self.query_one("#btn_start", Button).disabled = False
            self.query_one("#btn_cancel", Button).disabled = False


class ResearchScreen(Screen):
    """Screen for researching new topics."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static("[bold cyan]═══ Research New Topics ═══[/]\n"),

            Static("[bold yellow]Select Customer[/]"),
            Static("Use arrow keys to navigate, Enter to select", id="help_text"),
            OptionList(id="customer_list"),

            Static("\n"),
            Button("Start Research", id="btn_research", variant="primary"),

            Static("\n"),
            Container(
                Static("", id="progress_status"),
                ProgressBar(id="progress_bar", total=100, show_eta=False),
                id="progress_container"
            ),

            ScrollableContainer(
                Static("", id="research_results"),
                id="results_container"
            ),

            id="research_container",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Load customers when screen mounts."""
        # Hide progress container initially
        self.query_one("#progress_container").display = False
        await self.load_customers()

    async def load_customers(self) -> None:
        """Load customer list."""
        try:
            customers = await db.list_customers()
            customer_list = self.query_one("#customer_list", OptionList)

            if customers:
                for c in customers:
                    customer_list.add_option(
                        Option(f"- {c.name} - {c.company_name or 'No Company'}", id=str(c.id))
                    )
                self._customers = {str(c.id): c for c in customers}
            else:
                self.query_one("#help_text", Static).update(
                    "[yellow]No customers found. Please create a customer first.[/]"
                )
        except Exception as e:
            logger.error(f"Failed to load customers: {e}")
            self.query_one("#help_text", Static).update(f"[red]Error loading customers: {str(e)}[/]")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle customer selection."""
        self._selected_customer_id = event.option.id

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn_research":
            if hasattr(self, "_selected_customer_id") and self._selected_customer_id:
                self.start_research(self._selected_customer_id)
            else:
                results_widget = self.query_one("#research_results", Static)
                results_widget.update("[yellow]Please select a customer first.[/]")

    def start_research(self, customer_id: str) -> None:
        """Start research."""
        # Clear previous results
        self.query_one("#research_results", Static).update("")

        # Show progress container
        self.query_one("#progress_container").display = True
        self.query_one("#progress_bar", ProgressBar).update(progress=0)
        self.query_one("#progress_status", Static).update("[bold cyan]Starte Research...[/]")

        # Disable button
        self.query_one("#btn_research", Button).disabled = True

        # Run research in background worker
        self.run_worker(
            self._run_research_worker(customer_id),
            name="research_worker",
            group="research",
            exclusive=True
        )

    def _update_research_progress(self, message: str, step: int, total: int) -> None:
        """Update progress - works from both main thread and worker threads."""
        def update():
            progress_pct = (step / total) * 100
            self.query_one("#progress_bar", ProgressBar).update(progress=progress_pct)
            self.query_one("#progress_status", Static).update(f"[bold cyan]Step {step}/{total}:[/] {message}")
            self.refresh()

        # Check if we're on the main thread or a different thread
        if self.app._thread_id == threading.get_ident():
            # Same thread - schedule update for next tick to allow UI refresh
            self.app.call_later(update)
        else:
            # Different thread - use call_from_thread
            self.app.call_from_thread(update)

    async def _run_research_worker(self, customer_id: str):
        """Worker method to run research in background."""
        from uuid import UUID
        return await orchestrator.research_new_topics(
            UUID(customer_id),
            progress_callback=self._update_research_progress
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.worker.name != "research_worker":
            return

        results_widget = self.query_one("#research_results", Static)

        if event.state == WorkerState.SUCCESS:
            # Worker completed successfully
            topics = event.worker.result

            # Update progress to 100%
            self.query_one("#progress_bar", ProgressBar).update(progress=100)
            self.query_one("#progress_status", Static).update("[bold green]✓ Abgeschlossen![/]")

            # Format results
            output = "[bold green]✓ Research Complete![/]\n\n"
            output += f"[bold cyan]Found {len(topics)} new topic suggestions:[/]\n\n"

            for i, topic in enumerate(topics, 1):
                output += f"[bold]{i}. {topic.get('title', 'Unknown')}[/]\n"
                output += f"   [dim]Category:[/] {topic.get('category', 'N/A')}\n"

                fact = topic.get('fact', '')
                if fact:
                    if len(fact) > 200:
                        fact = fact[:197] + "..."
                    output += f"   [dim]Description:[/] {fact}\n"

                output += "\n"

            output += "[yellow]Topics saved to research results and ready for post creation.[/]"
            results_widget.update(output)
        elif event.state == WorkerState.ERROR:
            # Worker failed
            error = event.worker.error
            logger.exception(f"Research failed: {error}")
            self.query_one("#progress_status", Static).update("[bold red]✗ Fehler![/]")
            results_widget.update(
                f"[bold red]✗ Research Failed[/]\n\n"
                f"[red]Error: {str(error)}[/]\n\n"
                f"[yellow]Please check the error and try again.[/]"
            )
        elif event.state == WorkerState.CANCELLED:
            # Worker was cancelled
            results_widget.update("[yellow]Research cancelled[/]")

        # Hide progress container after a moment (keep visible briefly to show completion)
        # self.query_one("#progress_container").display = False

        # Re-enable button
        self.query_one("#btn_research", Button).disabled = False


class CreatePostScreen(Screen):
    """Screen for creating posts."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static("[bold cyan]═══ Create LinkedIn Post ═══[/]\n"),

            # Customer Selection
            Static("[bold yellow]1. Select Customer[/]"),
            Static("Use arrow keys to navigate, Enter to select", id="help_customer"),
            OptionList(id="customer_list"),

            # Topic Selection
            Static("\n[bold yellow]2. Select Topic[/]"),
            Static("Select a customer first to load topics...", id="help_topic"),
            OptionList(id="topic_list"),

            Static("\n"),
            Button("Create Post", id="btn_create", variant="primary"),

            Static("\n"),
            Container(
                Static("", id="progress_status"),
                ProgressBar(id="progress_bar", total=100, show_eta=False),
                Static("", id="iteration_info"),
                id="progress_container"
            ),

            ScrollableContainer(
                Static("", id="post_output"),
                id="output_container"
            ),
            id="create_container",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Load data when screen mounts."""
        # Hide progress container initially
        self.query_one("#progress_container").display = False
        await self.load_customers()

    async def load_customers(self) -> None:
        """Load customer list."""
        try:
            customers = await db.list_customers()
            customer_list = self.query_one("#customer_list", OptionList)

            if customers:
                for c in customers:
                    customer_list.add_option(
                        Option(f"- {c.name} - {c.company_name or 'No Company'}", id=str(c.id))
                    )
                self._customers = {str(c.id): c for c in customers}
            else:
                self.query_one("#help_customer", Static).update(
                    "[yellow]No customers found.[/]"
                )
        except Exception as e:
            logger.exception(f"Failed to load customers: {e}")
            self.query_one("#help_customer", Static).update(
                f"[red]Error loading customers: {str(e)}[/]"
            )

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle selection from option lists."""
        if event.option_list.id == "customer_list":
            # Customer selected
            self._selected_customer_id = event.option.id
            customer_name = self._customers[event.option.id].name
            self.query_one("#help_customer", Static).update(
                f"[green]✓ Selected: {customer_name}[/]"
            )
            # Load topics for this customer
            await self.load_topics(event.option.id)
        elif event.option_list.id == "topic_list":
            # Topic selected
            self._selected_topic_index = int(event.option.id)
            topic = self._topics[self._selected_topic_index]
            self.query_one("#help_topic", Static).update(
                f"[green]✓ Selected: {topic.get('title', 'Unknown')}[/]"
            )

    async def load_topics(self, customer_id) -> None:
        """Load ALL topics for customer from ALL research results."""
        try:
            from uuid import UUID
            # Get ALL research results, not just the latest
            all_research = await db.get_all_research(UUID(customer_id))

            topic_list = self.query_one("#topic_list", OptionList)
            topic_list.clear_options()

            # Collect all topics from all research results
            all_topics = []
            for research in all_research:
                if research.suggested_topics:
                    all_topics.extend(research.suggested_topics)

            if all_topics:
                self._topics = all_topics

                for i, t in enumerate(all_topics):
                    # Show title and category
                    display_text = f"- {t.get('title', 'Unknown')} [{t.get('category', 'N/A')}]"
                    topic_list.add_option(Option(display_text, id=str(i)))

                self.query_one("#help_topic", Static).update(
                    f"[cyan]{len(all_topics)} topics available from {len(all_research)} research(es) - select one to continue[/]"
                )
            else:
                self.query_one("#help_topic", Static).update(
                    "[yellow]No research topics found. Run research first.[/]"
                )
        except Exception as e:
            logger.exception(f"Failed to load topics: {e}")
            self.query_one("#help_topic", Static).update(
                f"[red]Error loading topics: {str(e)}[/]"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn_create":
            if not hasattr(self, "_selected_customer_id") or not self._selected_customer_id:
                output_widget = self.query_one("#post_output", Static)
                output_widget.update("[yellow]Please select a customer first.[/]")
                return

            if not hasattr(self, "_selected_topic_index") or self._selected_topic_index is None:
                output_widget = self.query_one("#post_output", Static)
                output_widget.update("[yellow]Please select a topic first.[/]")
                return

            from uuid import UUID
            topic = self._topics[self._selected_topic_index]
            self.create_post(UUID(self._selected_customer_id), topic)

    def create_post(self, customer_id, topic) -> None:
        """Create a post."""
        output_widget = self.query_one("#post_output", Static)

        # Clear previous output
        output_widget.update("")

        # Show progress container
        self.query_one("#progress_container").display = True
        self.query_one("#progress_bar", ProgressBar).update(progress=0)
        self.query_one("#progress_status", Static).update("[bold cyan]Starte Post-Erstellung...[/]")
        self.query_one("#iteration_info", Static).update("")

        # Disable button
        self.query_one("#btn_create", Button).disabled = True

        # Run post creation in background worker
        self.run_worker(
            self._run_create_post_worker(customer_id, topic),
            name="create_post_worker",
            group="create_post",
            exclusive=True
        )

    def _update_post_progress(self, message: str, iteration: int, max_iterations: int, score: int = None) -> None:
        """Update progress - works from both main thread and worker threads."""
        def update():
            # Calculate progress based on iteration
            if iteration == 0:
                progress_pct = 0
            else:
                progress_pct = (iteration / max_iterations) * 100

            self.query_one("#progress_bar", ProgressBar).update(progress=progress_pct)
            self.query_one("#progress_status", Static).update(f"[bold cyan]{message}[/]")

            if iteration > 0:
                score_text = f" | Score: {score}/100" if score else ""
                self.query_one("#iteration_info", Static).update(
                    f"[dim]Iteration {iteration}/{max_iterations}{score_text}[/]"
                )
            self.refresh()

        # Check if we're on the main thread or a different thread
        if self.app._thread_id == threading.get_ident():
            # Same thread - schedule update for next tick to allow UI refresh
            self.app.call_later(update)
        else:
            # Different thread - use call_from_thread
            self.app.call_from_thread(update)

    async def _run_create_post_worker(self, customer_id, topic):
        """Worker method to create post in background."""
        return await orchestrator.create_post(
            customer_id=customer_id,
            topic=topic,
            max_iterations=3,
            progress_callback=self._update_post_progress
        )

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.worker.name != "create_post_worker":
            return

        output_widget = self.query_one("#post_output", Static)

        if event.state == WorkerState.SUCCESS:
            # Worker completed successfully
            result = event.worker.result
            topic = self._topics[self._selected_topic_index]

            # Update progress to 100%
            self.query_one("#progress_bar", ProgressBar).update(progress=100)
            self.query_one("#progress_status", Static).update("[bold green]✓ Post erstellt![/]")
            self.query_one("#iteration_info", Static).update(
                f"[green]Final: {result['iterations']} Iterationen | Score: {result['final_score']}/100[/]"
            )

            # Format output
            output = f"[bold green]✓ Post Created Successfully![/]\n\n"
            output += f"[bold cyan]═══ Post Details ═══[/]\n"
            output += f"[bold]Topic:[/] {topic.get('title', 'Unknown')}\n"
            output += f"[bold]Iterations:[/] {result['iterations']}\n"
            output += f"[bold]Final Score:[/] {result['final_score']}/100\n"
            output += f"[bold]Approved:[/] {'✓ Yes' if result['approved'] else '✗ No (reached max iterations)'}\n\n"

            output += f"[bold cyan]═══ Final Post ═══[/]\n\n"
            output += f"[white]{result['final_post']}[/]\n\n"

            output += f"[bold cyan]═══════════════════[/]\n"
            output += f"[yellow]Post saved to database with ID: {result['post_id']}[/]"

            output_widget.update(output)
        elif event.state == WorkerState.ERROR:
            # Worker failed
            error = event.worker.error
            logger.exception(f"Post creation failed: {error}")
            self.query_one("#progress_status", Static).update("[bold red]✗ Fehler![/]")
            output_widget.update(
                f"[bold red]✗ Post Creation Failed[/]\n\n"
                f"[red]Error: {str(error)}[/]\n\n"
                f"[yellow]Please check the error and try again.[/]"
            )
        elif event.state == WorkerState.CANCELLED:
            # Worker was cancelled
            output_widget.update("[yellow]Post creation cancelled[/]")

        # Re-enable button
        self.query_one("#btn_create", Button).disabled = False


class StatusScreen(Screen):
    """Screen for viewing customer status."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield Container(
            Static("[bold cyan]═══ Customer Status ═══[/]\n\n"),
            ScrollableContainer(
                Static("Loading...", id="status_content"),
                id="status_scroll"
            ),
            Static("\n"),
            Button("Refresh", id="btn_refresh", variant="primary"),
        )
        yield Footer()

    def on_mount(self) -> None:
        """Load status when screen mounts."""
        self.load_status()

    def load_status(self) -> None:
        """Load and display status."""
        status_widget = self.query_one("#status_content", Static)
        status_widget.update("[yellow]Loading customer data...[/]")

        # Run status loading in background worker
        self.run_worker(
            self._run_load_status_worker(),
            name="load_status_worker",
            group="status",
            exclusive=True
        )

    async def _run_load_status_worker(self):
        """Worker method to load status in background."""
        customers = await db.list_customers()
        if not customers:
            return None

        output = ""
        for customer in customers:
            status = await orchestrator.get_customer_status(customer.id)

            output += f"[bold cyan]╔═══ {customer.name} ═══╗[/]\n"
            output += f"[bold]Customer ID:[/] {customer.id}\n"
            output += f"[bold]LinkedIn:[/] {customer.linkedin_url}\n"
            output += f"[bold]Company:[/] {customer.company_name or 'N/A'}\n\n"

            output += f"[bold yellow]Status:[/]\n"
            output += f"  Profile: {'[green]✓ Created[/]' if status['has_profile'] else '[red]✗ Missing[/]'}\n"
            output += f"  Analysis: {'[green]✓ Complete[/]' if status['has_analysis'] else '[red]✗ Missing[/]'}\n\n"

            output += f"[bold yellow]Content:[/]\n"
            output += f"  LinkedIn Posts: [cyan]{status['posts_count']}[/]\n"
            output += f"  Extracted Topics: [cyan]{status['topics_count']}[/]\n"
            output += f"  Generated Posts: [cyan]{status['generated_posts_count']}[/]\n"

            output += f"[bold cyan]╚{'═' * (len(customer.name) + 8)}╝[/]\n\n"

        return output

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.worker.name != "load_status_worker":
            return

        status_widget = self.query_one("#status_content", Static)

        if event.state == WorkerState.SUCCESS:
            # Worker completed successfully
            output = event.worker.result
            if output is None:
                status_widget.update(
                    "[yellow]No customers found.[/]\n"
                    "[dim]Create a new customer to get started.[/]"
                )
            else:
                status_widget.update(output)
        elif event.state == WorkerState.ERROR:
            # Worker failed
            error = event.worker.error
            logger.exception(f"Failed to load status: {error}")
            status_widget.update(
                f"[bold red]✗ Error Loading Status[/]\n\n"
                f"[red]{str(error)}[/]"
            )
        elif event.state == WorkerState.CANCELLED:
            # Worker was cancelled
            status_widget.update("[yellow]Status loading cancelled[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn_refresh":
            self.load_status()


class LinkedInWorkflowApp(App):
    """Main Textual application."""

    CSS = """
    Screen {
        align: center middle;
    }

    #menu_container {
        width: 60;
        height: auto;
        padding: 2;
        border: solid $primary;
        background: $surface;
    }

    #menu_container Button {
        width: 100%;
        margin: 1;
    }

    #welcome_text {
        text-align: center;
        padding: 1;
    }

    #form_container {
        width: 100%;
        height: 100%;
        padding: 2;
    }

    #form_container Input, #form_container TextArea {
        margin-bottom: 1;
    }

    #form_container Label {
        margin-top: 1;
        color: $text;
    }

    #form_container TextArea {
        height: 5;
    }

    #button_row {
        width: 100%;
        height: auto;
        margin: 1 0;
    }

    #button_row Button {
        margin: 0 1;
    }

    #status_container, #results_container, #output_container {
        min-height: 10;
        border: solid $accent;
        margin: 1 0;
        padding: 1;
    }

    #status_scroll {
        height: 30;
        border: solid $accent;
        margin-top: 1;
        padding: 1;
    }

    #research_container, #create_container {
        width: 90;
        height: auto;
        padding: 2;
        border: solid $primary;
        background: $surface;
    }

    #customer_list, #topic_list {
        height: 10;
        border: solid $accent;
        margin: 1 0;
    }

    #customer_list > .option-list--option,
    #topic_list > .option-list--option {
        padding: 1 1;
        margin-bottom: 1;
    }

    #help_text, #help_customer, #help_topic {
        color: $text-muted;
        margin-bottom: 1;
    }

    #progress_container {
        height: auto;
        padding: 1;
        margin: 1 0;
        border: solid $accent;
        background: $surface-darken-1;
    }

    #progress_bar {
        width: 100%;
        margin: 1 0;
    }

    #progress_status {
        text-align: center;
        margin-bottom: 1;
    }

    #iteration_info {
        text-align: center;
        margin-top: 1;
    }

    #title {
        text-align: center;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
    ]

    def on_mount(self) -> None:
        """Set up the application on mount."""
        self.title = "LinkedIn Post Creation System"
        self.sub_title = "Multi-Agent AI Workflow"
        self.push_screen(WelcomeScreen())


def run_app():
    """Run the TUI application."""
    app = LinkedInWorkflowApp()
    app.run()
