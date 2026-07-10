import { HttpClient } from '@angular/common/http';
import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
} from '@angular/core';
import { Modal } from 'bootstrap';

type ChatRole = 'assistant' | 'user';

interface ChatMessage {
  role: ChatRole;
  content: string;
  error?: boolean;
  timestamp: string;
}

interface AgentResponse {
  answer: string;
}

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css'],
  standalone: false,
})
export class AppComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('chatMessages') chatMessages?: ElementRef<HTMLDivElement>;

  readonly placeholderText = 'Digita la tua richiesta';

  query = '';
  loading = false;
  resetSuccess = false;
  showScrollBottom = false;
  activeChatMessages: ChatMessage[] = [];

  private readonly onMessagesScroll = () => this.checkScroll();

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.seedIntroMessage();
  }

  ngAfterViewInit(): void {
    this.chatMessages?.nativeElement.addEventListener('scroll', this.onMessagesScroll);
    this.checkDisclaimer();
    this.scrollToBottom();
  }

  ngOnDestroy(): void {
    this.chatMessages?.nativeElement.removeEventListener('scroll', this.onMessagesScroll);
  }

  checkDisclaimer(): void {
    const accepted = sessionStorage.getItem('disclaimerAccepted');
    if (accepted) return;

    const modalEl = document.getElementById('disclaimerModal');
    if (!modalEl) return;

    Modal.getOrCreateInstance(modalEl, {
      backdrop: 'static',
      keyboard: false,
    }).show();
  }

  acceptDisclaimer(): void {
    sessionStorage.setItem('disclaimerAccepted', 'true');

    const modalEl = document.getElementById('disclaimerModal');
    if (!modalEl) return;

    Modal.getOrCreateInstance(modalEl).hide();
  }

  askAgent(event?: Event): void {
    event?.preventDefault();

    const userMsg = this.query.trim();
    if (!userMsg || this.loading) return;

    this.query = '';
    this.removeIntroMessage();
    const history = this.chatHistory();
    this.pushMessage('user', userMsg);
    this.loading = true;

    this.http
      .post<AgentResponse>(
        '/api/chat',
        { message: userMsg, history },
        { headers: { 'Content-Type': 'application/json' } },
      )
      .subscribe({
        next: (response) => {
          this.pushMessage('assistant', response.answer);
          this.loading = false;
        },
        error: (error) => {
          console.error("Errore durante l'invio del messaggio:", error);
          this.pushMessage(
            'assistant',
            'Assistente temporaneamente non disponibile. Riprova piu tardi.',
            true,
          );
          this.loading = false;
        },
      });
  }

  handleKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey && !this.loading) {
      event.preventDefault();
      this.askAgent(event);
    }
  }

  autoResize(event: Event): void {
    const textarea = event.target as HTMLTextAreaElement;
    textarea.style.height = '84px';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }

  checkScroll(): void {
    const el = this.chatMessages?.nativeElement;
    if (!el) return;

    this.showScrollBottom =
      el.scrollHeight > el.clientHeight &&
      el.scrollTop + el.clientHeight < el.scrollHeight - 24;
  }

  scrollToBottom(): void {
    window.setTimeout(() => {
      const el = this.chatMessages?.nativeElement;
      if (!el) return;

      el.scrollTop = el.scrollHeight;
      this.showScrollBottom = false;
    });
  }

  resetChat(): void {
    this.activeChatMessages = [];
    this.seedIntroMessage();
    this.resetSuccess = true;
    this.hideResetAlertLater();
  }

  private chatHistory(): Array<Pick<ChatMessage, 'role' | 'content'>> {
    return this.activeChatMessages
      .filter((message) => !message.error)
      .slice(-12)
      .map(({ role, content }) => ({ role, content }));
  }

  private seedIntroMessage(): void {
    if (this.activeChatMessages.length) return;

    this.pushMessage(
      'assistant',
      "Esplora le risorse del catalogo e l'interoperabilita semantica con l'aiuto dell'Intelligenza Artificiale. Puoi chiedermi:\n\n- Quali sono le risorse semantiche disponibili nel catalogo\n- Le pubblicazioni di un ente specifico e il loro utilizzo\n- Informazioni sull'interoperabilita semantica",
    );
  }

  private removeIntroMessage(): void {
    this.activeChatMessages = this.activeChatMessages.filter(
      (message) =>
        !(
          message.role === 'assistant' &&
          message.content.includes('Esplora le risorse del catalogo')
        ),
    );
  }

  private pushMessage(role: ChatRole, content: string, error = false): void {
    this.activeChatMessages.push({
      role,
      content,
      error,
      timestamp: new Date().toISOString(),
    });

    this.scrollToBottom();
  }

  private hideResetAlertLater(): void {
    window.setTimeout(() => {
      this.resetSuccess = false;
    }, 3000);
  }
}
